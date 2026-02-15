"""aipm ticket - Manage local tickets."""

from __future__ import annotations

import re
from pathlib import Path

import click
from rich.console import Console

from aipm.config import get_project_root
from aipm.horizons import HORIZONS, validate_horizon
from aipm.utils import format_markdown_ticket, git_stage_files, sanitize_name

console = Console()


def _get_ticket_files(local_dir: Path) -> list[Path]:
    """Get all ticket files, handling both old .md files and new ISSUE.md in folders."""
    ticket_files = []
    for item in local_dir.iterdir():
        if item.is_file() and item.suffix == ".md":
            # Old format
            ticket_files.append(item)
        elif item.is_dir() and (item / "ISSUE.md").exists():
            # New format
            ticket_files.append(item / "ISSUE.md")
    return sorted(ticket_files)


def _get_next_ticket_number(local_dir: Path) -> int:
    """Find the next sequential ticket number in the local directory."""
    if not local_dir.exists():
        return 1

    max_num = 0
    for item in local_dir.iterdir():
        num = 0
        if item.is_file() and item.suffix == ".md":
            # Old format: 0001_title.md
            match = re.match(r"^(\d+)_", item.name)
            if match:
                num = int(match.group(1))
        elif item.is_dir() and (item / "ISSUE.md").exists():
            # New format: 000001_title/ISSUE.md
            match = re.match(r"^(\d+)_", item.name)
            if match:
                num = int(match.group(1))
        if num > max_num:
            max_num = num

    return max_num + 1


def cmd_ticket_add(
    title: str | None = None,
    status: str = "open",
    priority: str = "",
    assignee: str = "",
    description: str = "",
    summary: str = "",
    labels: str = "",
    horizon: str = "",
    due: str = "",
    repo: str = "",
    offline: bool = False,
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

    if not horizon:
        if interactive:
            horizon = click.prompt(
                "Horizon",
                default="sometime",
                type=click.Choice(list(HORIZONS), case_sensitive=False),
            )
        else:
            horizon = "sometime"

    # Validate horizon
    try:
        horizon = validate_horizon(horizon)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return

    if interactive and not due:
        due = click.prompt("Due date (YYYY-MM-DD, optional)", default="", show_default=False)

    if interactive and not assignee:
        assignee = click.prompt("Assignee (optional)", default="", show_default=False)

    if interactive and not repo:
        repo = click.prompt("Repo (git URL or local path, optional)", default="", show_default=False)

    label_list = [item.strip() for item in labels.split(",") if item.strip()] if labels else []

    # If due date is set but horizon was left at default, infer horizon
    if due and horizon == "sometime":
        from aipm.horizons import infer_horizon_from_due

        horizon = infer_horizon_from_due(due)

    # Generate sequential number
    num = _get_next_ticket_number(local_dir)
    key = f"L-{num:06d}"
    sanitized = sanitize_name(title)
    dirname = f"{num:06d}_{sanitized}"
    ticket_dir = local_dir / dirname
    ticket_dir.mkdir(parents=True, exist_ok=True)
    issue_file = ticket_dir / "ISSUE.md"

    content = format_markdown_ticket(
        key=key,
        title=title,
        status=status,
        assignee=assignee,
        priority=priority,
        labels=label_list or None,
        description=description,
        summary=summary,
        url="",
        repo=repo,
        source_type="local",
        horizon=horizon,
        due=due,
    )

    issue_file.write_text(content)

    console.print(f"[green]Created ticket:[/green] {key} — {title}")
    console.print(f"  Horizon: [cyan]{horizon}[/cyan]")
    if due:
        console.print(f"  Due:     [cyan]{due}[/cyan]")
    console.print(f"  File: tickets/local/{dirname}/ISSUE.md")

    # Stage the file
    git_stage_files([issue_file], cwd=project_root)


def _extract_title_from_path(file_path: Path) -> str:
    """Extract title from ticket file path (folder name or filename)."""
    if file_path.name == "ISSUE.md":
        # New folder structure: extract from folder name
        folder_name = file_path.parent.name
        # Split on first underscore to get title part
        parts = folder_name.split("_", 1)
        if len(parts) > 1:
            return parts[1].replace("_", " ")
        return folder_name
    else:
        # Old flat structure: use filename stem
        return file_path.stem.replace("_", " ")


def cmd_ticket_list(offline: bool = False) -> None:
    """List all local tickets."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    ticket_files = _get_ticket_files(local_dir)
    if not ticket_files:
        console.print("[yellow]No local tickets found.[/yellow]")
        return

    from rich.table import Table

    table = Table(title="Local Tickets")
    table.add_column("Key", style="cyan")
    table.add_column("Title")
    table.add_column("Status", style="green")
    table.add_column("Horizon", style="magenta")
    table.add_column("Due")
    table.add_column("Priority")
    table.add_column("Assignee")

    for f in ticket_files:
        content = f.read_text()
        info = _parse_local_ticket(content)
        title_fallback = _extract_title_from_path(f)
        table.add_row(
            info.get("key", ""),
            info.get("title", title_fallback),
            info.get("status", ""),
            info.get("horizon", ""),
            info.get("due", ""),
            info.get("priority", ""),
            info.get("assignee", ""),
        )

    console.print(table)


def _parse_local_ticket(content: str) -> dict[str, str]:
    """Parse a local ticket markdown file with front matter or table format."""
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

                    # Use content as description - everything after frontmatter
                    description_start = i + 1
                    if description_start < len(lines):
                        # For frontmatter format, everything after the --- is the description
                        desc_content = "\n".join(lines[description_start:]).strip()
                        if desc_content:
                            info["description"] = desc_content
                    return info
            except yaml.YAMLError:
                pass  # Fall back to old parsing
    else:
        # Fallback to old table parsing
        for line in lines:
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

    # Extract description from old format
    desc = _extract_description(content)
    if desc:
        info["description"] = desc

    return info


def _extract_description(content: str) -> str:
    """Extract the description section from ticket markdown."""
    lines = content.split("\n")

    # Check if this is frontmatter format
    if lines and lines[0].strip() == "---":
        # Find the closing ---
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                # Everything after the closing --- is the description
                desc_lines = lines[i + 1 :]
                return "\n".join(desc_lines).strip()

    # Old format: look for ## Description section first
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

    desc = "\n".join(desc_lines).strip()
    if desc:
        return desc

    # If no ## Description section, extract everything after the table
    # Find the end of the table (last |---| line)
    table_end = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|---"):
            table_end = i

    if table_end > 0 and table_end + 1 < len(lines):
        # Everything after the table is description
        desc_lines = lines[table_end + 1 :]
        return "\n".join(desc_lines).strip()

    return ""


def cmd_ticket_upgrade(offline: bool = False, structure: bool = False) -> None:
    """Scan local tickets for missing fields and interactively fill them in."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    if not local_dir.exists():
        console.print("[yellow]No local tickets directory found.[/yellow]")
        return

    if structure:
        # Migrate to new folder structure
        console.print("[bold]Migrating tickets to new folder-based structure...[/bold]")
        migrated = 0
        for item in local_dir.iterdir():
            if item.is_file() and item.suffix == ".md":
                # Old format: 0001_title.md -> migrate to 000001_title/ISSUE.md
                match = re.match(r"^(\d+)_(.+)\.md$", item.name)
                if match:
                    num_str, title_part = match.groups()
                    num = int(num_str)
                    new_num_str = f"{num:06d}"
                    new_dirname = f"{new_num_str}_{title_part}"
                    new_dir = local_dir / new_dirname
                    new_dir.mkdir(exist_ok=True)
                    new_file = new_dir / "ISSUE.md"

                    # Read old content and update key if needed
                    content = item.read_text()
                    # Update key in content if it's old format
                    content = re.sub(r'^key: "L-\d{4}"$', f'key: "L-{new_num_str}"', content, flags=re.MULTILINE)

                    new_file.write_text(content)
                    item.unlink()  # Remove old file
                    migrated += 1
                    console.print(f"  Migrated {item.name} -> {new_dirname}/ISSUE.md")

        console.print(f"[green]Migrated {migrated} ticket(s) to new structure.[/green]")
        return

    ticket_files = _get_ticket_files(local_dir)
    if not ticket_files:
        console.print("[yellow]No local tickets found.[/yellow]")
        return

    # Fields that every ticket should have
    required_fields = ["horizon", "priority"]
    # Fields that are nice to have but truly optional
    optional_fields = ["due", "assignee", "repo"]
    upgraded = 0
    skipped = 0

    console.print(f"[bold]Scanning {len(ticket_files)} local ticket(s) for missing fields...[/bold]\n")

    for filepath in ticket_files:
        content = filepath.read_text()
        info = _parse_local_ticket(content)
        description = _extract_description(content)

        missing_required = [f for f in required_fields if not info.get(f)]
        missing_optional = [f for f in optional_fields if not info.get(f)]

        if not missing_required:
            continue

        missing = missing_required + missing_optional

        key = info.get("key", filepath.stem)
        title = info.get("title", filepath.stem)
        console.print(f"[cyan]{key}[/cyan]: {title}")
        console.print(f"  Missing: [yellow]{', '.join(missing)}[/yellow]")

        if not click.confirm("  Update this ticket?", default=True):
            skipped += 1
            console.print()
            continue

        # Prompt for each missing field
        new_horizon = info.get("horizon", "")
        new_due = info.get("due", "")
        new_priority = info.get("priority", "")
        new_assignee = info.get("assignee", "")
        new_repo = info.get("repo", "")

        if "horizon" in missing:
            new_horizon = click.prompt(
                "  Horizon",
                default="sometime",
                type=click.Choice(list(HORIZONS), case_sensitive=False),
            )

        if "due" in missing:
            new_due = click.prompt("  Due date (YYYY-MM-DD, optional)", default="", show_default=False)

        if "priority" in missing:
            new_priority = click.prompt(
                "  Priority",
                default="medium",
                type=click.Choice(["critical", "high", "medium", "low"], case_sensitive=False),
            )

        if "assignee" in missing:
            new_assignee = click.prompt("  Assignee (optional)", default="", show_default=False)

        if "repo" in missing:
            new_repo = click.prompt("  Repo (git URL or local path, optional)", default="", show_default=False)

        # If due date set but horizon is still default, infer
        if new_due and new_horizon == "sometime":
            from aipm.horizons import infer_horizon_from_due

            new_horizon = infer_horizon_from_due(new_due)
            console.print(f"  Inferred horizon: [cyan]{new_horizon}[/cyan]")

        # Parse labels from existing content
        labels_str = info.get("labels", "")
        label_list = [item.strip() for item in labels_str.split(",") if item.strip()] if labels_str else None

        # Rewrite the file with all fields
        new_content = format_markdown_ticket(
            key=info.get("key", key),
            title=info.get("title", title),
            status=info.get("status", "open"),
            assignee=new_assignee,
            priority=new_priority,
            labels=label_list,
            description=description,
            url=info.get("url", ""),
            repo=new_repo,
            source_type=info.get("source", "local"),
            horizon=new_horizon,
            due=new_due,
        )

        filepath.write_text(new_content)
        upgraded += 1
        console.print("  [green]Updated![/green]\n")

    # Stage changed files
    if upgraded:
        git_stage_files(ticket_files, cwd=project_root)

    already_complete = len(ticket_files) - upgraded - skipped
    console.print(f"[bold]Done:[/bold] {upgraded} upgraded, {skipped} skipped, {already_complete} already complete.")
