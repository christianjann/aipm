"""aipm commit - Commit the updated tickets and plan."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from aipm.config import ProjectConfig, get_project_root
from aipm.utils import git_commit, git_has_staged_changes, git_stage_files, git_staged_diff

console = Console()


def _generate_commit_message(diff: str, config: ProjectConfig, offline: bool = False) -> str:
    """Generate a commit message from the diff, using Copilot unless offline."""
    if offline:
        return _generate_commit_message_fallback(diff, config)
    try:
        from github_copilot import Copilot

        copilot = Copilot()
        prompt = (
            "Generate a concise, conventional-commit-style commit message for the following changes. "
            "Use the format: 'type(scope): description'. "
            "The changes are from an AI project management tool that syncs tickets and plans.\n\n"
            f"Project: {config.name}\n\n"
            f"```diff\n{diff[:4000]}\n```"
        )
        response = copilot.chat(prompt)
        # Take first line as commit message
        return response.strip().split("\n")[0]
    except Exception:
        return _generate_commit_message_fallback(diff, config)


def _generate_commit_message_fallback(diff: str, config: ProjectConfig) -> str:
    """Generate a commit message without AI."""
    lines = diff.split("\n")
    files_changed: set[str] = set()

    for line in lines:
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) > 1:
                files_changed.add(parts[1])

    ticket_files = [f for f in files_changed if f.startswith("tickets/")]
    plan_files = [f for f in files_changed if f in ("milestones.md", "goals.md")]

    parts = []
    if ticket_files:
        parts.append(f"sync {len(ticket_files)} tickets")
    if plan_files:
        parts.append(f"update {', '.join(plan_files)}")
    if not parts:
        parts.append(f"update {len(files_changed)} files")

    now = datetime.now().strftime("%Y-%m-%d")
    return f"chore(aipm): {', '.join(parts)} [{now}]"


def cmd_commit(offline: bool = False) -> None:
    """Commit the updated tickets and plan, offline disables Copilot."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    config = ProjectConfig.load(project_root)

    # Check for staged changes
    if not git_has_staged_changes(cwd=project_root):
        # Try to stage common AIPM files
        console.print("[dim]No staged changes. Looking for AIPM files to stage...[/dim]")

        files_to_stage: list[Path] = []
        tickets_dir = project_root / "tickets"
        if tickets_dir.exists():
            files_to_stage.extend(tickets_dir.rglob("*.md"))

        for f in ("milestones.md", "goals.md", "aipm.toml"):
            p = project_root / f
            if p.exists():
                files_to_stage.append(p)

        if files_to_stage:
            git_stage_files(files_to_stage, cwd=project_root)
            console.print(f"[green]Staged {len(files_to_stage)} AIPM files.[/green]")
        else:
            console.print("[yellow]Nothing to commit.[/yellow]")
            return

    # Get diff for message generation
    diff = git_staged_diff(cwd=project_root)
    if not diff.strip():
        console.print("[yellow]No changes detected in staged files.[/yellow]")
        return

    # Generate commit message
    suggested_message = _generate_commit_message(diff, config, offline=offline)
    console.print(f"\nSuggested commit message: [cyan]{suggested_message}[/cyan]")

    message = click.prompt("Commit message", default=suggested_message)

    # Commit
    git_commit(message, cwd=project_root)
    console.print(f"\n[bold green]Committed![/bold green] {message}")
