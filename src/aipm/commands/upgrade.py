"""aipm upgrade - Upgrade existing tickets by filling in missing fields."""

from __future__ import annotations

import re
from pathlib import Path

import click
from rich.console import Console

from aipm.config import get_project_root
from aipm.horizons import HORIZONS
from aipm.utils import format_markdown_ticket

console = Console()


def cmd_upgrade(offline: bool = False, structure: bool = False) -> None:
    """Upgrade existing tickets by filling in missing fields or converting structure."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    if not local_dir.exists():
        console.print("[yellow]No local tickets found to upgrade.[/yellow]")
        return

    tickets_upgraded = 0

    # Get all ticket files (both old flat format and new directory format)
    ticket_files = []
    for item in local_dir.iterdir():
        if item.is_file() and item.suffix == ".md":
            # Old format
            ticket_files.append(item)
        elif item.is_dir() and (item / "ISSUE.md").exists():
            # New format
            ticket_files.append(item / "ISSUE.md")

    for ticket_file in sorted(ticket_files):
        ticket_data = _parse_ticket(ticket_file)
        if not ticket_data:
            continue

        # Check if ticket is already in frontmatter format
        content = ticket_file.read_text()
        is_frontmatter = content.startswith("---")

        missing_fields = _get_missing_fields(ticket_data)

        # Check if key needs updating based on filename
        key_from_filename = _get_key_from_filename(ticket_file)
        current_key = ticket_data.get("key", "")
        key_needs_update = key_from_filename and key_from_filename != current_key

        # Determine if we should upgrade this ticket
        should_upgrade = True if structure else bool(missing_fields) or not is_frontmatter or key_needs_update

        if not should_upgrade:
            continue

        console.print(f"\n[bold]Ticket: {ticket_data.get('title', ticket_file.stem)}[/bold]")
        console.print(f"File: {ticket_file.relative_to(project_root)}")

        if structure:
            console.print("[dim]Upgrading to new directory structure...[/dim]")
            # For structure upgrade, don't prompt - just do it
            do_upgrade = True
        else:
            do_upgrade = click.confirm("Upgrade this ticket?", default=True)

        if not do_upgrade:
            continue

        if structure:
            # For structure upgrade, just move to directory structure without changing content
            _upgrade_directory_structure(ticket_file, ticket_data)
            tickets_upgraded += 1
            console.print(f"[green]Upgraded {ticket_file.name}[/green]")
            continue

        # Update key if needed
        if key_needs_update:
            console.print(
                f"[yellow]Key mismatch: file suggests '{key_from_filename}', ticket has '{current_key}'[/yellow]"
            )
            if click.confirm(f"Update key to '{key_from_filename}'?", default=True):
                ticket_data["key"] = key_from_filename
                console.print(f"[dim]Updated key: {current_key} → {key_from_filename}[/dim]")

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

        # If --structure is used, also upgrade the directory structure
        if structure:
            _upgrade_directory_structure(ticket_file, ticket_data)

        tickets_upgraded += 1
        console.print(f"[green]Upgraded {ticket_file.name}[/green]")

    if tickets_upgraded == 0:
        console.print("[yellow]No tickets needed upgrading.[/yellow]")
    else:
        console.print(f"[green]Upgraded {tickets_upgraded} ticket(s).[/green]")


def _parse_ticket(ticket_file: Path) -> dict[str, str]:
    """Parse a ticket markdown file with YAML front matter."""
    content = ticket_file.read_text()
    lines = content.split("\n")

    data: dict[str, str] = {}

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
                            data[k] = ", ".join(str(item) for item in v)
                        else:
                            data[k] = str(v) if v is not None else ""

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
                        data["description"] = "\n".join(desc_lines).strip()
                    return data
            except yaml.YAMLError:
                pass  # Fall back to old parsing
    else:
        # Fallback to old table parsing for backward compatibility
        # Extract title from # header
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
        in_description = False
        for line in lines:
            if line.startswith("|") and "**" in line:
                in_table = True
                parts = line.split("|")
                if len(parts) >= 3:
                    field = parts[1].strip().strip("*").strip().lower()
                    value = parts[2].strip()
                    data[field] = value

            elif in_table and not line.startswith("|"):
                # Check if this is the description header
                if line.strip() == "## Description":
                    in_description = True
                    continue
                # Description content
                if in_description:
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


def _upgrade_directory_structure(ticket_file: Path, ticket_data: dict[str, str]) -> None:
    """Upgrade ticket from file to directory structure."""
    from aipm.utils import sanitize_name

    # Extract number from key (e.g., "L-0001" -> "0001")
    key = ticket_data.get("key", "")
    number_part = key.split("-")[-1] if "-" in key else key

    # Zero-pad to 6 digits
    padded_number = f"{int(number_part):06d}"

    # Update the key to use the new format
    new_key = f"L-{padded_number}"
    ticket_data["key"] = new_key

    # Sanitize title
    title = ticket_data.get("title", "")
    sanitized_title = sanitize_name(title, max_length=60)

    # Create directory name
    dir_name = f"{padded_number}_{sanitized_title}"
    ticket_dir = ticket_file.parent / dir_name

    # Create directory
    ticket_dir.mkdir(exist_ok=True)

    # Move file to ISSUE.md
    new_file = ticket_dir / "ISSUE.md"
    ticket_file.rename(new_file)

    # Update the ticket file with the new key
    _update_ticket_file(new_file, ticket_data)

    console.print(f"[dim]Moved to directory: {dir_name}/ISSUE.md[/dim]")
    console.print(f"[dim]Updated key: {key} → {new_key}[/dim]")


def _update_ticket_file(ticket_file: Path, ticket_data: dict[str, str]) -> None:
    """Update a ticket file with new data in front matter format."""
    # Check if original file ends with newline
    original_content = ticket_file.read_text()
    ends_with_newline = original_content.endswith("\n")

    # Convert string labels back to list if present
    labels = None
    if "labels" in ticket_data and ticket_data["labels"].strip():
        labels = [label.strip() for label in ticket_data["labels"].split(",") if label.strip()]

    content = format_markdown_ticket(
        key=ticket_data.get("key", ""),
        title=ticket_data.get("title", ""),
        status=ticket_data.get("status", "open"),
        assignee=ticket_data.get("assignee", ""),
        priority=ticket_data.get("priority", "medium"),
        labels=labels,
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

    ticket_file.write_text(content)


def _get_key_from_filename(ticket_file: Path) -> str | None:
    """Extract the expected ticket key from the filename/directory name."""
    # For files in directory structure: 000001_title/ISSUE.md
    if ticket_file.name == "ISSUE.md" and ticket_file.parent.is_dir():
        dir_name = ticket_file.parent.name
        # Extract number from directory name (e.g., "000001" from "000001_title")
        number_match = re.match(r"^(\d+)", dir_name)
        if number_match:
            number = int(number_match.group(1))
            return f"L-{number:06d}"

    # For flat files: 0001_title.md
    elif ticket_file.is_file() and ticket_file.suffix == ".md":
        file_name = ticket_file.name
        # Extract number from filename (e.g., "0001" from "0001_title.md")
        number_match = re.match(r"^(\d+)", file_name)
        if number_match:
            number = int(number_match.group(1))
            return f"L-{number:06d}"

    return None
