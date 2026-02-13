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
    horizon: str = "",
    due: str = "",
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

    label_list = [item.strip() for item in labels.split(",") if item.strip()] if labels else []

    # If due date is set but horizon was left at default, infer horizon
    if due and horizon == "sometime":
        from aipm.horizons import infer_horizon_from_due

        horizon = infer_horizon_from_due(due)

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
        horizon=horizon,
        due=due,
    )

    filepath.write_text(content)

    console.print(f"[green]Created ticket:[/green] {key} — {title}")
    console.print(f"  Horizon: [cyan]{horizon}[/cyan]")
    if due:
        console.print(f"  Due:     [cyan]{due}[/cyan]")
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
    table.add_column("Horizon", style="magenta")
    table.add_column("Due")
    table.add_column("Priority")
    table.add_column("Assignee")

    for f in sorted(local_dir.glob("*.md")):
        content = f.read_text()
        info = _parse_local_ticket(content)
        table.add_row(
            info.get("key", ""),
            info.get("title", f.stem),
            info.get("status", ""),
            info.get("horizon", ""),
            info.get("due", ""),
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


def _extract_description(content: str) -> str:
    """Extract the description section from ticket markdown."""
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
    return "\n".join(desc_lines).strip()


def cmd_ticket_upgrade() -> None:
    """Scan local tickets for missing fields and interactively fill them in."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    local_dir = project_root / "tickets" / "local"
    if not local_dir.exists() or not any(local_dir.glob("*.md")):
        console.print("[yellow]No local tickets to upgrade.[/yellow]")
        return

    # Fields that every ticket should have
    required_fields = ["horizon", "priority"]
    # Fields that are nice to have but truly optional
    optional_fields = ["due", "assignee"]
    upgraded = 0
    skipped = 0

    files = sorted(local_dir.glob("*.md"))
    console.print(f"[bold]Scanning {len(files)} local ticket(s) for missing fields...[/bold]\n")

    for filepath in files:
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
            source_type=info.get("source", "local"),
            horizon=new_horizon,
            due=new_due,
        )

        filepath.write_text(new_content)
        upgraded += 1
        console.print("  [green]Updated![/green]\n")

    # Stage changed files
    if upgraded:
        git_stage_files(list(local_dir.glob("*.md")), cwd=project_root)

    already_complete = len(files) - upgraded - skipped
    console.print(f"[bold]Done:[/bold] {upgraded} upgraded, {skipped} skipped, {already_complete} already complete.")
