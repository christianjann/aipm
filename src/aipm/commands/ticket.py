"""aipm ticket - Manage local tickets."""

from __future__ import annotations

import re
from pathlib import Path

import click
from rich.console import Console

from aipm.config import get_project_root
from aipm.utils import format_markdown_ticket, git_stage_files, sanitize_name

console = Console()


def _next_ticket_number(local_dir: Path) -> int:
    """Find the next sequential ticket number in the local directory."""
    if not local_dir.exists():
        return 1

    max_num = 0
    for f in local_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            match = re.match(r"^(\d+)_", f.name)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

    return max_num + 1


def cmd_ticket_add(
    title: str | None = None,
    status: str = "open",
    priority: str = "",
    assignee: str = "",
    description: str = "",
    labels: str = "",
) -> None:
    """Create a new local ticket."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)

    # Interactive prompts only when title is not provided (fully interactive mode)
    interactive = title is None

    if not title:
        title = click.prompt("Ticket title")

    if interactive and not description:
        description = click.prompt("Description (optional)", default="", show_default=False)

    if not priority:
        if interactive:
            priority = click.prompt(
                "Priority",
                default="medium",
                type=click.Choice(["critical", "high", "medium", "low"], case_sensitive=False),
            )
        else:
            priority = "medium"

    if interactive and not assignee:
        assignee = click.prompt("Assignee (optional)", default="", show_default=False)

    label_list = [item.strip() for item in labels.split(",") if item.strip()] if labels else []

    # Generate sequential number
    num = _next_ticket_number(local_dir)
    key = f"L-{num:04d}"
    sanitized = sanitize_name(title)
    filename = f"{num:04d}_{sanitized}.md"
    filepath = local_dir / filename

    content = format_markdown_ticket(
        key=key,
        title=title,
        status=status,
        assignee=assignee,
        priority=priority,
        labels=label_list or None,
        description=description,
        url="",
        source_type="local",
    )

    filepath.write_text(content)

    console.print(f"[green]Created ticket:[/green] {key} — {title}")
    console.print(f"  File: tickets/local/{filename}")

    # Stage the file
    git_stage_files([filepath], cwd=project_root)


def cmd_ticket_list() -> None:
    """List all local tickets."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    if not local_dir.exists() or not any(local_dir.glob("*.md")):
        console.print("[yellow]No local tickets found.[/yellow]")
        return

    from rich.table import Table

    table = Table(title="Local Tickets")
    table.add_column("Key", style="cyan")
    table.add_column("Title")
    table.add_column("Status", style="green")
    table.add_column("Priority")
    table.add_column("Assignee")

    for f in sorted(local_dir.glob("*.md")):
        content = f.read_text()
        info = _parse_local_ticket(content)
        table.add_row(
            info.get("key", ""),
            info.get("title", f.stem),
            info.get("status", ""),
            info.get("priority", ""),
            info.get("assignee", ""),
        )

    console.print(table)


def _parse_local_ticket(content: str) -> dict[str, str]:
    """Parse a local ticket markdown file."""
    info: dict[str, str] = {}
    for line in content.split("\n"):
        if line.startswith("# "):
            # "# L-0001: Title" -> extract key and title
            heading = line[2:].strip()
            if ": " in heading:
                info["key"], info["title"] = heading.split(": ", 1)
            else:
                info["title"] = heading
        if "| **" in line and "** |" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                field = parts[1].strip().strip("*").strip()
                value = parts[2].strip()
                info[field.lower()] = value
    return info
