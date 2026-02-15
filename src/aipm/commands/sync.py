"""aipm sync - Sync issues from all sources to the tickets directory."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress

from aipm.config import ProjectConfig, SourceConfig, get_project_root
from aipm.sources.base import IssueSource, Ticket
from aipm.sources.github_source import GitHubSource
from aipm.sources.jira_source import JiraSource
from aipm.utils import format_markdown_ticket, git_has_staged_changes, git_stage_files, sanitize_name

console = Console()


def create_source(config: SourceConfig) -> IssueSource:
    """Create an issue source from configuration."""
    if config.type == "jira":
        return JiraSource(config)
    elif config.type == "github":
        return GitHubSource(config)
    else:
        raise ValueError(f"Unknown source type: {config.type}")


def write_ticket_file(ticket: Ticket, tickets_dir: Path) -> Path:
    """Write a ticket to a markdown file, return the file path."""
    sanitized = sanitize_name(ticket.title)
    # Use the key in the filename (remove special chars like #)
    key_clean = ticket.key.replace("#", "").replace("/", "_")
    filename = f"{key_clean}_{sanitized}.md"

    filepath = tickets_dir / filename

    content = format_markdown_ticket(
        key=ticket.key,
        title=ticket.title,
        status=ticket.status,
        assignee=ticket.assignee,
        priority=ticket.priority,
        labels=ticket.labels,
        description=ticket.description,
        url=ticket.url,
        source_type=ticket.source_type,
        extra_fields=ticket.extra_fields,
    )

    filepath.write_text(content)
    return filepath


def cmd_sync(offline: bool = False) -> None:
    """Sync issues from all configured sources to the tickets directory."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    config = ProjectConfig.load(project_root)

    if not config.sources:
        console.print(
            "[yellow]No sources configured. Run 'aipm add jira <URL>' or 'aipm add github <URL>' first.[/yellow]"
        )
        return

    tickets_dir = project_root / "tickets"
    tickets_dir.mkdir(exist_ok=True)

    all_written_files: list[Path] = []
    total_tickets = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Syncing sources...", total=len(config.sources))

        for source_config in config.sources:
            source_name = source_config.name or source_config.project_key or source_config.type
            progress.update(task, description=f"Syncing {source_name}...")

            try:
                source = create_source(source_config)
                source.connect()
                tickets = source.fetch_issues()

                # Create source-specific directory
                source_dir = tickets_dir / source_name
                source_dir.mkdir(exist_ok=True)

                for ticket in tickets:
                    filepath = write_ticket_file(ticket, source_dir)
                    all_written_files.append(filepath)
                    total_tickets += 1

                console.print(f"  [green]✓[/green] {source_name}: {len(tickets)} tickets synced")

            except Exception as e:
                console.print(f"  [red]✗[/red] {source_name}: {e}")

            progress.advance(task)

    console.print(f"\n[bold]Synced {total_tickets} tickets from {len(config.sources)} source(s).[/bold]")

    # Handle git staging
    if all_written_files:
        if git_has_staged_changes(cwd=project_root):
            # There are already staged changes, ask user
            if click.confirm("There are already staged changes. Stage the synced ticket files too?", default=True):
                git_stage_files(all_written_files, cwd=project_root)
                console.print("[green]Ticket files staged.[/green]")
            else:
                console.print("[dim]Ticket files not staged. You can stage them manually.[/dim]")
        else:
            # Nothing staged, auto-stage
            git_stage_files(all_written_files, cwd=project_root)
            console.print("[green]Ticket files staged for commit.[/green]")
