"""aipm init - Initialize a new AIPM project."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from aipm.config import CONFIG_FILENAME, ProjectConfig

console = Console()


def cmd_init() -> None:
    """Initialize a new AIPM project in the current directory."""
    cwd = Path.cwd()

    # Check if already initialized
    if (cwd / CONFIG_FILENAME).exists():
        console.print(f"[yellow]Project already initialized ({CONFIG_FILENAME} exists).[/yellow]")
        if not click.confirm("Reinitialize?", default=False):
            return

    # Query project info
    name = click.prompt("Project name", default=cwd.name)
    description = click.prompt("Project description", default="")

    # Create directory structure
    tickets_dir = cwd / "tickets"
    generated_dir = cwd / "generated"

    tickets_dir.mkdir(exist_ok=True)
    generated_dir.mkdir(exist_ok=True)

    console.print("  [green]Created[/green] tickets/")
    console.print("  [green]Created[/green] generated/")

    # Create milestones.md
    milestones_path = cwd / "milestones.md"
    if not milestones_path.exists():
        milestones_path.write_text(
            f"# {name} - Milestones\n\n"
            "## Upcoming\n\n"
            "<!-- Add milestones here -->\n\n"
            "## Completed\n\n"
            "<!-- Completed milestones will be moved here -->\n"
        )
        console.print("  [green]Created[/green] milestones.md")

    # Create goals.md
    goals_path = cwd / "goals.md"
    if not goals_path.exists():
        goals_path.write_text(
            f"# {name} - Goals\n\n"
            "## Primary Goals\n\n"
            "<!-- Define project goals here -->\n\n"
            "## Secondary Goals\n\n"
            "<!-- Additional goals -->\n"
        )
        console.print("  [green]Created[/green] goals.md")

    # Create project README
    readme_path = cwd / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            f"# {name}\n\n"
            f"{description}\n\n"
            "## Structure\n\n"
            "- `tickets/` - Synced issue tickets from connected sources\n"
            "- `milestones.md` - Project milestones and timeline\n"
            "- `goals.md` - Project goals\n"
            "- `generated/` - Generated reports (plan, kanban, etc.)\n"
            f"- `{CONFIG_FILENAME}` - AIPM configuration\n"
        )
        console.print("  [green]Created[/green] README.md")

    # Create .gitkeep in generated
    gitkeep = generated_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("")

    # Save config
    config = ProjectConfig(name=name, description=description)
    config.save(cwd)
    console.print(f"  [green]Created[/green] {CONFIG_FILENAME}")

    console.print(f"\n[bold green]Project '{name}' initialized![/bold green]")
    console.print("Next steps:")
    console.print("  1. Add issue sources: [cyan]aipm add jira <URL>[/cyan] or [cyan]aipm add github <URL>[/cyan]")
    console.print("  2. Sync issues: [cyan]aipm sync[/cyan]")
