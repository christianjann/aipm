"""aipm upgrade - Upgrade existing tickets by filling in missing fields."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from aipm.config import get_project_root
from aipm.horizons import HORIZONS

console = Console()


def cmd_upgrade(offline: bool = False) -> None:
    """Upgrade existing tickets by filling in missing fields interactively."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    if not local_dir.exists():
        console.print("[yellow]No local tickets found to upgrade.[/yellow]")
        return

    tickets_upgraded = 0

    for ticket_file in sorted(local_dir.glob("*.md")):
        ticket_data = _parse_ticket(ticket_file)
        if not ticket_data:
            continue

        missing_fields = _get_missing_fields(ticket_data)
        if not missing_fields:
            continue

        console.print(f"\n[bold]Ticket: {ticket_data.get('title', ticket_file.stem)}[/bold]")
        console.print(f"File: {ticket_file.name}")

        if not click.confirm("Upgrade this ticket?", default=True):
            continue

        # Prompt for missing fields
        for field in missing_fields:
            if field == "status":
                ticket_data[field] = click.prompt(
                    "Status",
                    default="open",
                    type=click.Choice(["open", "in-progress", "completed"]),
                )
            elif field == "priority":
                ticket_data[field] = click.prompt(
                    "Priority",
                    default="medium",
                    type=click.Choice(["critical", "high", "medium", "low"]),
                )
            elif field == "horizon":
                ticket_data[field] = click.prompt(
                    "Horizon",
                    default="sometime",
                    type=click.Choice(list(HORIZONS)),
                )
            elif field == "assignee":
                ticket_data[field] = click.prompt("Assignee (optional)", default="")
            elif field == "repo":
                ticket_data[field] = click.prompt("Repo (git URL or local path, optional)", default="")
            elif field == "due":
                ticket_data[field] = click.prompt("Due date (YYYY-MM-DD, optional)", default="")

        # Rewrite the ticket file
        _update_ticket_file(ticket_file, ticket_data)
        tickets_upgraded += 1
        console.print(f"[green]Upgraded {ticket_file.name}[/green]")

    if tickets_upgraded == 0:
        console.print("[yellow]No tickets needed upgrading.[/yellow]")
    else:
        console.print(f"[green]Upgraded {tickets_upgraded} ticket(s).[/green]")


def _parse_ticket(ticket_file: Path) -> dict[str, str]:
    """Parse a ticket markdown file into a dict."""
    content = ticket_file.read_text()
    lines = content.split("\n")
    data: dict[str, str] = {}

    # Extract title and key from # header
    for line in lines:
        if line.startswith("# "):
            heading = line[2:].strip()
            if ": " in heading:
                data["key"], data["title"] = heading.split(": ", 1)
            else:
                data["title"] = heading
            break

    # Extract fields from table
    in_table = False
    description_lines = []
    for line in lines:
        if line.startswith("|") and "**" in line:
            in_table = True
            parts = line.split("|")
            if len(parts) >= 3:
                field = parts[1].strip().strip("*").strip().lower()
                value = parts[2].strip()
                data[field] = value
        elif in_table and line.strip() == "":
            # End of table
            break
        elif in_table and not line.startswith("|"):
            # Description starts
            description_lines.append(line)

    data["description"] = "\n".join(description_lines).strip()

    return data


def _get_missing_fields(ticket_data: dict[str, str]) -> list[str]:
    """Get list of missing fields for a ticket."""
    required_fields = ["status", "priority", "horizon"]
    optional_fields = ["assignee", "repo", "due"]

    missing = []
    for field in required_fields + optional_fields:
        if field not in ticket_data or not ticket_data[field].strip():
            missing.append(field)

    return missing


def _update_ticket_file(ticket_file: Path, ticket_data: dict[str, str]) -> None:
    """Update a ticket file by adding missing fields to the existing table."""
    content = ticket_file.read_text()
    lines = content.split("\n")

    # Find the table
    table_start = -1
    table_end = -1
    for i, line in enumerate(lines):
        if line.startswith("| Field | Value |"):
            table_start = i + 2  # Start after header
        elif table_start != -1 and line.strip() == "" and table_end == -1:
            table_end = i
            break

    if table_start == -1:
        # No table found, skip
        return

    if table_end == -1:
        table_end = len(lines)

    # Get existing fields
    existing_fields = set()
    for i in range(table_start, table_end):
        line = lines[i]
        if "| **" in line and "** |" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                field = parts[1].strip().strip("*").strip().lower()
                existing_fields.add(field)

    # Add missing fields
    insert_index = table_end
    for field in ["status", "priority", "horizon", "assignee", "repo", "due"]:
        value = ticket_data.get(field, "").strip()
        if value and field not in existing_fields:
            row = f"| **{field.title()}** | {value} |"
            lines.insert(insert_index, row)
            insert_index += 1

    # Write back
    content = "\n".join(lines)
    ticket_file.write_text(content)
