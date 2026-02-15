"""aipm check - Verify ticket completion against a repo or directory."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from aipm.config import get_project_root
from aipm.horizons import horizon_sort_key
from aipm.utils import (
    ModelUnavailableError,
    copilot_chat,
    git_commit,
    git_has_staged_changes,
    git_stage_files,
    select_copilot_model,
)

console = Console()

# How many recent commits to scan
_GIT_LOG_LIMIT = 50


@dataclass
class CommitInfo:
    """A single git commit."""

    hash: str
    message: str


def _parse_all_tickets(project_root: Path) -> list[dict[str, str]]:
    """Parse all ticket markdown files and return them sorted by horizon urgency."""
    tickets_dir = project_root / "tickets"
    if not tickets_dir.exists():
        return []

    results: list[dict[str, str]] = []
    for md_file in sorted(tickets_dir.rglob("*.md")):
        info = _parse_ticket_file(md_file)
        info["_path"] = str(md_file)
        results.append(info)

    # Sort by horizon urgency (most urgent first)
    results.sort(key=lambda t: horizon_sort_key(t.get("horizon", "sometime")))
    return results


def _parse_ticket_file(filepath: Path) -> dict[str, str]:
    """Parse a ticket markdown file into a dict of fields."""
    content = filepath.read_text()
    lines = content.split("\n")
    info: dict[str, str] = {}

    # Check if it starts with front matter
    if lines and lines[0] == "---":
        # Parse YAML front matter
        front_matter_lines = []
        i = 1
        while i < len(lines) and lines[i] != "---":
            front_matter_lines.append(lines[i])
            i += 1

        if front_matter_lines:
            import yaml

            try:
                front_matter = yaml.safe_load("\n".join(front_matter_lines))
                if isinstance(front_matter, dict):
                    # Convert all values to strings, handle lists
                    for k, v in front_matter.items():
                        if isinstance(v, list):
                            info[k] = ", ".join(str(item) for item in v)
                        else:
                            info[k] = str(v) if v is not None else ""

                    # Use content as description
                    description_start = i + 1
                    if description_start < len(lines):
                        desc_lines = []
                        in_description = False
                        for line in lines[description_start:]:
                            if line.startswith("## Description"):
                                in_description = True
                                continue
                            if in_description:
                                desc_lines.append(line)
                        info["description"] = "\n".join(desc_lines).strip()
                    return info
            except yaml.YAMLError:
                pass  # Fall back to old parsing

    # Fallback to old table parsing
    for line in content.split("\n"):
        if line.startswith("# "):
            heading = line[2:].strip()
            if ": " in heading:
                info["key"], info["title"] = heading.split(": ", 1)
            else:
                info["title"] = heading
        if "| **" in line and "** |" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                field_name = parts[1].strip().strip("*").strip()
                value = parts[2].strip()
                info[field_name.lower()] = value

    # Extract description
    lines = content.split("\n")
    in_desc = False
    desc_lines: list[str] = []
    for line in lines:
        if line.startswith("## Description"):
            in_desc = True
            continue
        if in_desc:
            if line.startswith("## "):
                break
            desc_lines.append(line)
    info["description"] = "\n".join(desc_lines).strip()

    return info


def _analysis_suggests_done(analysis: str) -> bool:
    """Check if the analysis text indicates the ticket is DONE."""
    # Look for "Status: DONE" or "**Status**: DONE" patterns
    lower = analysis.lower()
    # Match variations: "status: done", "**status**: done", "status:** done"
    return bool(re.search(r"\bstatus\b[*:| ]*\s*done\b", lower))


def _update_ticket_status(ticket_path: Path, new_status: str) -> None:
    """Update the Status field in a ticket markdown file."""
    from aipm.utils import format_markdown_ticket

    # Check if original file ends with newline
    original_content = ticket_path.read_text()
    ends_with_newline = original_content.endswith("\n")

    # Parse the current ticket
    ticket_data = _parse_ticket_file(ticket_path)
    ticket_data["status"] = new_status

    # Rewrite the file
    content = format_markdown_ticket(
        key=ticket_data.get("key", ""),
        title=ticket_data.get("title", ""),
        status=ticket_data.get("status", "open"),
        assignee=ticket_data.get("assignee", ""),
        priority=ticket_data.get("priority", "medium"),
        labels=ticket_data.get("labels", "").split(", ") if ticket_data.get("labels") else None,
        description=ticket_data.get("description", ""),
        summary=ticket_data.get("summary", ""),
        url=ticket_data.get("url", ""),
        repo=ticket_data.get("repo", ""),
        source_type=ticket_data.get("source", "local"),
        horizon=ticket_data.get("horizon", "sometime"),
        due=ticket_data.get("due", ""),
    )

    # Preserve trailing newline
    if ends_with_newline and not content.endswith("\n"):
        content += "\n"
    elif not ends_with_newline and content.endswith("\n"):
        content = content.rstrip("\n")

    ticket_path.write_text(content)


def _resolve_repo_path(repo: str, project_root: Path) -> Path | None:
    """Resolve a repo string to a local Path, or None for remote URLs."""
    repo_path = Path(repo).expanduser()
    if not repo_path.is_absolute():
        repo_path = (project_root / repo_path).resolve()
    if repo_path.is_dir():
        return repo_path
    return None


def _get_git_log(repo_path: Path) -> list[CommitInfo]:
    """Get the recent git log as a list of CommitInfo (hash + message)."""
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return []

    result = subprocess.run(
        ["git", "log", f"-{_GIT_LOG_LIMIT}", "--format=%H %s", "--no-decorate"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    commits: list[CommitInfo] = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split(" ", 1)
        if len(parts) == 2:
            commits.append(CommitInfo(hash=parts[0], message=parts[1]))
    return commits


def _build_keywords(ticket_info: dict[str, str]) -> list[str]:
    """Extract search keywords from a ticket's title and description."""
    title = ticket_info.get("title", "")
    description = ticket_info.get("description", "")
    key = ticket_info.get("key", "")

    text = f"{title} {description}".lower()
    # Split into meaningful words (3+ chars), deduplicate
    stop_words = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "have",
        "are",
        "was",
        "were",
        "been",
        "being",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "not",
        "but",
        "all",
        "also",
        "into",
        "over",
        "such",
        "than",
        "then",
        "when",
        "what",
        "which",
        "where",
        "who",
        "how",
        "has",
        "had",
        "its",
        "our",
        "out",
        "use",
        "add",
        "new",
        "set",
    }
    words = []
    for word in text.split():
        # Strip punctuation
        cleaned = "".join(c for c in word if c.isalnum() or c in "-_")
        if len(cleaned) >= 3 and cleaned not in stop_words:
            words.append(cleaned)

    # Also add the ticket key (e.g. L-0001)
    if key:
        words.append(key.lower())

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique


def _filter_commits_by_message(
    commits: list[CommitInfo],
    keywords: list[str],
) -> list[CommitInfo]:
    """Filter commits whose message matches any of the keywords."""
    matching: list[CommitInfo] = []
    for commit in commits:
        msg_lower = commit.message.lower()
        if any(kw in msg_lower for kw in keywords):
            matching.append(commit)
    return matching


def _extract_hashes(response: str) -> set[str]:
    """Extract 7-8 char hex hashes from a Copilot response.

    Handles formats like:
    - plain: ``90262d6c``
    - backtick-wrapped: ```90262d6c```
    - list items: ``- 90262d6c Add something``
    - mixed: ``90262d6c: relevant because...``
    """
    # Find all sequences of 7-40 hex chars that look like git hashes
    return {m.group()[:8] for m in re.finditer(r"\b[0-9a-f]{7,40}\b", response)}


def _check_with_copilot(
    ticket_info: dict[str, str],
    commits: list[CommitInfo],
    *,
    debug: bool = False,
    offline: bool = False,
) -> tuple[list[CommitInfo], str, bool]:
    """Ask Copilot to identify relevant commits and analyze ticket completion, unless offline.

    Returns (relevant_commits, analysis_text, used_copilot).
    """
    key = ticket_info.get("key", "?")
    title = ticket_info.get("title", "?")
    description = ticket_info.get("description", "")
    status = ticket_info.get("status", "")
    horizon = ticket_info.get("horizon", "")

    commit_list = "\n".join(f"- {c.hash[:8]} {c.message}" for c in commits)

    prompt = (
        "You are an AI project manager assistant. Given a ticket and a list of recent git commits, "
        "analyze whether this ticket's task has been completed based on the commit messages.\n\n"
        "First, list the short hashes (first 8 chars) of ALL relevant commits, one per line, "
        "prefixed with COMMITS:\n\n"
        "Then provide your analysis:\n"
        "1. **Status**: DONE, IN PROGRESS, or NOT STARTED\n"
        "2. **Confidence**: High, Medium, or Low\n"
        "3. **Evidence**: Which commits address the task (reference by hash)\n"
        "4. **Remaining work**: If not done, what still needs to happen\n\n"
        f"## Ticket {key}: {title}\n"
        f"- Current status: {status}\n"
        f"- Horizon: {horizon}\n"
        f"- Description: {description}\n\n"
        f"## Recent Commits\n{commit_list}\n"
    )

    if offline:
        # Fallback: keyword matching + structured summary
        keywords = _build_keywords(ticket_info)
        relevant = _filter_commits_by_message(commits, keywords)
        fallback_text = _check_fallback(ticket_info, relevant)
        return relevant, fallback_text, False

    if debug:
        console.print(Panel(prompt, title="Copilot prompt", border_style="yellow"))

    try:
        response = copilot_chat(prompt)

        if not response or not response.strip():
            console.print("  [dim]Copilot returned empty response, falling back to keywords[/dim]")
            raise ValueError("Empty response")

        if debug:
            console.print(Panel(response, title="Copilot response", border_style="yellow"))
        else:
            console.print(f"  [dim]Copilot: {response.strip()[:200]}[/dim]")

        # Extract relevant commit hashes from response
        relevant_hashes = _extract_hashes(response)
        known_hashes = {c.hash[:8] for c in commits}
        relevant_hashes &= known_hashes

        relevant = [c for c in commits if c.hash[:8] in relevant_hashes] if relevant_hashes else []

        return relevant, response, True
    except ModelUnavailableError:
        new_model = select_copilot_model()
        try:
            response = copilot_chat(prompt, model=new_model)
            if response and response.strip():
                if debug:
                    console.print(Panel(response, title="Copilot response", border_style="yellow"))
                else:
                    console.print(f"  Copilot: {response.strip()[:200]}")
                relevant_hashes = _extract_hashes(response)
                known_hashes = {c.hash[:8] for c in commits}
                relevant_hashes &= known_hashes
                relevant = [c for c in commits if c.hash[:8] in relevant_hashes] if relevant_hashes else []
                return relevant, response, True
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: keyword matching + structured summary
    keywords = _build_keywords(ticket_info)
    relevant = _filter_commits_by_message(commits, keywords)
    fallback_text = _check_fallback(ticket_info, relevant)
    return relevant, fallback_text, False


def _check_fallback(ticket_info: dict[str, str], relevant_commits: list[CommitInfo]) -> str:
    """Fallback when Copilot is unavailable — structured summary for manual review."""
    key = ticket_info.get("key", "?")
    title = ticket_info.get("title", "?")
    description = ticket_info.get("description", "(no description)")
    status = ticket_info.get("status", "?")

    lines = [
        f"## {key}: {title}\n",
        f"**Current status:** {status}",
        f"**Description:** {description}\n",
        "---\n",
        f"**{len(relevant_commits)} potentially relevant commit(s) found** (matched by keywords — review manually):\n",
    ]
    for commit in relevant_commits:
        lines.append(f"- `{commit.hash[:8]}` {commit.message}")

    return "\n".join(lines)


def cmd_check(ticket_key: str | None = None, limit: int = 0, *, debug: bool = False, offline: bool = False) -> None:
    """Check ticket completion against configured repos, offline disables Copilot."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    all_tickets = _parse_all_tickets(project_root)
    if not all_tickets:
        console.print("[yellow]No tickets found.[/yellow]")
        return

    # Filter to tickets with a repo configured
    checkable = [t for t in all_tickets if t.get("repo")]

    # If a specific ticket key was requested, filter to that
    if ticket_key:
        checkable = [t for t in all_tickets if t.get("key", "").lower() == ticket_key.lower()]
        if not checkable:
            console.print(f"[red]Ticket '{ticket_key}' not found.[/red]")
            return
        if not checkable[0].get("repo"):
            console.print(
                f"[yellow]Ticket '{ticket_key}' has no repo configured.[/yellow]\n"
                "Add one with [cyan]aipm ticket upgrade[/cyan] or edit the ticket file."
            )
            return

    if not checkable:
        console.print(
            "[yellow]No tickets have a repo configured.[/yellow]\n"
            "Add a repo to a ticket with:\n"
            "  [cyan]aipm ticket add -t 'My task' --repo /path/to/project[/cyan]\n"
            "  [cyan]aipm ticket upgrade[/cyan]  (to add repo to existing tickets)"
        )
        return

    # Skip completed tickets
    checkable = [t for t in checkable if t.get("status", "").lower() not in ("done", "closed", "completed")]

    if not checkable:
        console.print("[green]All tickets with repos are already completed![/green]")
        return

    # Apply limit
    if limit > 0:
        checkable = checkable[:limit]

    total = len(checkable)
    console.print(f"[bold]Checking {total} ticket(s) against their repos...[/bold]\n")

    for i, ticket in enumerate(checkable, 1):
        key = ticket.get("key", "?")
        title = ticket.get("title", "?")
        horizon = ticket.get("horizon", "?")
        repo = ticket.get("repo", "")

        description = ticket.get("description", "")
        console.print(f"[bold cyan]({i}/{total})[/bold cyan] {key}: {title}")
        if description:
            console.print(f"  [dim]{description[:120]}[/dim]")
        console.print(f"  Horizon: [magenta]{horizon}[/magenta]  Repo: [dim]{repo}[/dim]")

        # Step 1: Resolve repo and get git log
        repo_path = _resolve_repo_path(repo, project_root)
        if repo_path is None:
            console.print("  [yellow]Repo path not found or is a remote URL (not yet supported).[/yellow]\n")
            continue

        with console.status("  Reading git log..."):
            commits = _get_git_log(repo_path)

        if not commits:
            console.print("  [yellow]No git history found.[/yellow]\n")
            continue

        console.print(f"  Found [cyan]{len(commits)}[/cyan] recent commits")

        # Analyze commits against ticket (single Copilot call on messages only)
        with console.status("  Analyzing commits..."):
            relevant, result, used_copilot = _check_with_copilot(ticket, commits, debug=debug, offline=offline)

        if relevant:
            console.print(f"  [green]{len(relevant)}[/green] relevant commit(s) found:")
            for c in relevant:
                console.print(f"    [dim]{c.hash[:8]}[/dim] {c.message}")
        else:
            console.print("  [yellow]No matching commits found.[/yellow]")

        done = _analysis_suggests_done(result)
        mode_note = f"Mode: {'Copilot' if used_copilot else 'Offline/Fallback'}"
        md = Markdown(result + f"\n\n{mode_note}")
        border = "green" if done else "blue"
        console.print(Panel(md, title=f"{key}: {title}", border_style=border))

        # Ask whether to close the ticket.
        # Options: y = close, N = skip, c = close + commit
        ticket_path = Path(ticket.get("_path", ""))
        if ticket_path.exists():
            default_hint = "Y/n/c" if done else "y/N/c"
            choice = click.prompt(
                f"  Close ticket {key}? [{default_hint}] (c=commit)",
                type=click.Choice(["y", "n", "c"], case_sensitive=False),
                default="y" if done else "n",
                show_choices=False,
                show_default=False,
            )
            if choice in ("y", "c"):
                _update_ticket_status(ticket_path, "completed")
                if choice == "c":
                    git_stage_files([ticket_path], cwd=project_root)
                    git_commit(f"AIPM: Marked {key} as completed", cwd=project_root)
                    console.print(f"  [green]{key} marked as completed and committed.[/green]")
                else:
                    if not git_has_staged_changes(cwd=project_root):
                        git_stage_files([ticket_path], cwd=project_root)
                    console.print(f"  [green]{key} marked as completed.[/green]")

        console.print()
