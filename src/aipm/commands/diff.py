"""aipm diff - Summarize staged changes using git and Copilot."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from aipm.config import get_project_root
from aipm.utils import git_staged_diff

console = Console()


def _read_project_context(project_root: Path) -> str:
    """Read project context files for the AI summary."""
    context_parts: list[str] = []

    # Read goals
    goals_path = project_root / "goals.md"
    if goals_path.exists():
        context_parts.append(f"## Project Goals\n{goals_path.read_text()}")

    # Read milestones
    milestones_path = project_root / "milestones.md"
    if milestones_path.exists():
        context_parts.append(f"## Milestones\n{milestones_path.read_text()}")

    return "\n\n".join(context_parts)


def _summarize_with_copilot(diff: str, context: str, offline: bool = False) -> str:
    """Use GitHub Copilot SDK to summarize the diff, unless offline."""
    if offline:
        return _summarize_fallback(diff)
    try:
        from github_copilot import Copilot

        copilot = Copilot()
        prompt = (
            "You are an AI project manager assistant. Based on the project context and the git diff below, "
            "provide a concise summary of the changes. Focus on:\n"
            "1. What tickets/issues were updated\n"
            "2. Key status changes\n"
            "3. How these changes relate to project goals and milestones\n"
            "4. A suggested commit message\n\n"
            f"## Project Context\n{context}\n\n"
            f"## Git Diff\n```diff\n{diff[:8000]}\n```"
        )
        response = copilot.chat(prompt)
        return response
    except Exception:
        return _summarize_fallback(diff)


def _summarize_fallback(diff: str) -> str:
    """Fallback summary when Copilot is not available."""
    lines = diff.split("\n")
    files_changed: set[str] = set()
    additions = 0
    deletions = 0

    for line in lines:
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) > 1:
                files_changed.add(parts[1])
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    summary_parts = [
        "# Staged Changes Summary\n",
        f"**Files changed:** {len(files_changed)}",
        f"**Additions:** {additions}",
        f"**Deletions:** {deletions}\n",
        "## Files\n",
    ]

    for f in sorted(files_changed):
        summary_parts.append(f"- `{f}`")

    # Categorize changes
    ticket_files = [f for f in files_changed if f.startswith("tickets/")]
    if ticket_files:
        summary_parts.append(f"\n## Ticket Updates ({len(ticket_files)} files)\n")
        for f in sorted(ticket_files):
            summary_parts.append(f"- `{f}`")

    plan_files = [f for f in files_changed if f in ("milestones.md", "goals.md")]
    if plan_files:
        summary_parts.append("\n## Plan Updates\n")
        for f in sorted(plan_files):
            summary_parts.append(f"- `{f}`")

    return "\n".join(summary_parts)


def cmd_diff(offline: bool = False) -> None:
    """Summarize the staged changes using AI or offline fallback."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    diff = git_staged_diff(cwd=project_root)

    if not diff.strip():
        console.print("[yellow]No staged changes found.[/yellow]")
        console.print("Stage some changes first with [cyan]git add[/cyan] or [cyan]aipm sync[/cyan].")
        return

    context = _read_project_context(project_root)

    console.print("[bold]Analyzing staged changes...[/bold]\n")

    summary = _summarize_with_copilot(diff, context, offline=offline)
    md = Markdown(summary)
    console.print(md)
