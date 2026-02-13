"""aipm check - Verify ticket completion against a repo or directory."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from aipm.config import get_project_root
from aipm.horizons import horizon_sort_key
from aipm.utils import git_has_staged_changes, git_stage_files

console = Console()

# How many recent commits to scan
_GIT_LOG_LIMIT = 50
# Max diff size (characters) to send to Copilot
_MAX_DIFF_SIZE = 12000


@dataclass
class CommitInfo:
    """A single git commit."""

    hash: str
    message: str
    diff: str = ""


@dataclass
class CheckResult:
    """Result of checking a ticket against its repo."""

    relevant_commits: list[CommitInfo] = field(default_factory=list)
    analysis: str = ""


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
    info: dict[str, str] = {}

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
    content = ticket_path.read_text()
    # Replace the status row in the markdown table
    updated = re.sub(
        r"(\|\s*\*\*Status\*\*\s*\|)\s*[^|]+(\|)",
        rf"\1 {new_status} \2",
        content,
    )
    ticket_path.write_text(updated)


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


def _get_commit_diff(repo_path: Path, commit_hash: str) -> str:
    """Get the full diff for a single commit."""
    result = subprocess.run(
        ["git", "show", "--stat", "--patch", commit_hash, "--no-decorate"],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    if result.returncode == 0:
        return result.stdout
    return ""


def _build_keywords(ticket_info: dict[str, str]) -> list[str]:
    """Extract search keywords from a ticket's title and description."""
    title = ticket_info.get("title", "")
    description = ticket_info.get("description", "")
    key = ticket_info.get("key", "")

    text = f"{title} {description}".lower()
    # Split into meaningful words (3+ chars), deduplicate
    stop_words = {
        "the", "and", "for", "that", "this", "with", "from", "have", "are",
        "was", "were", "been", "being", "will", "would", "could", "should",
        "can", "may", "not", "but", "all", "also", "into", "over", "such",
        "than", "then", "when", "what", "which", "where", "who", "how",
        "has", "had", "its", "our", "out", "use", "add", "new", "set",
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


def _check_with_copilot_messages(
    ticket_info: dict[str, str],
    commits: list[CommitInfo],
) -> list[CommitInfo]:
    """Ask Copilot which commit messages are relevant to the ticket.

    Falls back to keyword matching when Copilot is unavailable.
    """
    key = ticket_info.get("key", "?")
    title = ticket_info.get("title", "?")
    description = ticket_info.get("description", "")

    commit_list = "\n".join(f"- {c.hash[:8]} {c.message}" for c in commits)

    prompt = (
        "You are a project manager assistant. Given a ticket and a list of git commits, "
        "return ONLY the short hashes (first 8 chars) of commits that are relevant to this ticket. "
        "Return one hash per line, nothing else. If none are relevant, return NONE.\n\n"
        f"## Ticket {key}: {title}\n"
        f"Description: {description}\n\n"
        f"## Commits\n{commit_list}\n"
    )

    try:
        from github_copilot import Copilot

        copilot = Copilot()
        response = copilot.chat(prompt)
        # Parse hashes from response
        relevant_hashes = set()
        for line in response.strip().split("\n"):
            token = line.strip().lstrip("- ")
            if len(token) >= 7 and all(c in "0123456789abcdef" for c in token[:8]):
                relevant_hashes.add(token[:8])
        if relevant_hashes:
            return [c for c in commits if c.hash[:8] in relevant_hashes]
        return []
    except Exception:
        # Fallback: keyword matching
        keywords = _build_keywords(ticket_info)
        return _filter_commits_by_message(commits, keywords)


def _check_with_copilot_diff(
    ticket_info: dict[str, str],
    relevant_commits: list[CommitInfo],
) -> str:
    """Analyze the diffs of relevant commits against the ticket."""
    key = ticket_info.get("key", "?")
    title = ticket_info.get("title", "?")
    description = ticket_info.get("description", "")
    status = ticket_info.get("status", "")
    horizon = ticket_info.get("horizon", "")

    # Build diff context, truncating if needed
    diff_parts: list[str] = []
    total_size = 0
    for commit in relevant_commits:
        if not commit.diff:
            continue
        entry = f"### Commit {commit.hash[:8]}: {commit.message}\n```diff\n{commit.diff}\n```\n"
        if total_size + len(entry) > _MAX_DIFF_SIZE:
            remaining = _MAX_DIFF_SIZE - total_size
            if remaining > 200:
                diff_parts.append(entry[:remaining] + "\n... (truncated)")
            break
        diff_parts.append(entry)
        total_size += len(entry)

    diff_context = "\n".join(diff_parts)

    prompt = (
        "You are an AI project manager assistant. Analyze whether this ticket's task "
        "has been completed based on the relevant git commits and their diffs.\n\n"
        "Provide:\n"
        "1. **Status**: DONE, IN PROGRESS, or NOT STARTED\n"
        "2. **Confidence**: High, Medium, or Low\n"
        "3. **Evidence**: Which commits address the task and what they changed\n"
        "4. **Remaining work**: If not done, what still needs to happen\n\n"
        f"## Ticket {key}: {title}\n"
        f"- Current status: {status}\n"
        f"- Horizon: {horizon}\n"
        f"- Description: {description}\n\n"
        f"## Relevant Commits & Diffs\n{diff_context}\n"
    )

    try:
        from github_copilot import Copilot

        copilot = Copilot()
        return copilot.chat(prompt)
    except Exception:
        return _check_fallback(ticket_info, relevant_commits)


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
        f"**{len(relevant_commits)} potentially relevant commit(s) found** "
        "(Copilot unavailable — review manually):\n",
    ]
    for commit in relevant_commits:
        lines.append(f"- `{commit.hash[:8]}` {commit.message}")

    return "\n".join(lines)


def cmd_check(ticket_key: str | None = None, limit: int = 0) -> None:
    """Check ticket completion against configured repos.

    For each ticket with a repo, scans the git log and:
    1. Filters commits by message relevance (via Copilot or keyword fallback)
    2. Fetches diffs only for matching commits
    3. Asks Copilot to analyze whether the task is fulfilled
    """
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

        console.print(f"[bold cyan]({i}/{total})[/bold cyan] {key}: {title}")
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

        # Step 2: Filter commits by message relevance
        with console.status("  Filtering commits by relevance..."):
            relevant = _check_with_copilot_messages(ticket, commits)

        if not relevant:
            console.print("  [yellow]No matching commits found.[/yellow]")
            console.print(
                Panel("**Status:** NOT STARTED\n\nNo commits found that match this ticket.",
                      title=key, border_style="red")
            )
            console.print()
            continue

        console.print(f"  [green]{len(relevant)}[/green] relevant commit(s) found:")
        for c in relevant:
            console.print(f"    [dim]{c.hash[:8]}[/dim] {c.message}")

        # Step 3: Fetch diffs for matching commits
        with console.status("  Fetching diffs..."):
            for commit in relevant:
                commit.diff = _get_commit_diff(repo_path, commit.hash)

        # Step 4: Analyze with Copilot
        with console.status("  Analyzing with Copilot..."):
            result = _check_with_copilot_diff(ticket, relevant)

        done = _analysis_suggests_done(result)
        md = Markdown(result)
        border = "green" if done else "blue"
        console.print(Panel(md, title=f"{key}", border_style=border))

        # Ask whether to close the ticket.
        # When Copilot says DONE → default yes. Otherwise still ask, default no.
        ticket_path = Path(ticket.get("_path", ""))
        if ticket_path.exists() and click.confirm(f"  Close ticket {key}?", default=done):
            _update_ticket_status(ticket_path, "completed")
            if not git_has_staged_changes(cwd=project_root):
                git_stage_files([ticket_path], cwd=project_root)
            console.print(f"  [green]{key} marked as completed.[/green]")

        console.print()
