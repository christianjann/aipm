"""aipm add - Add issue sources to the project."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import click
from rich.console import Console

from aipm.config import ProjectConfig, SourceConfig

console = Console()


def cmd_add_jira(url: str) -> None:
    """Add a Jira project as an issue source."""
    config = ProjectConfig.load()
    project_root = Path.cwd()

    # Parse URL to extract project key if possible
    parsed = urlparse(url)
    # Remove trailing path components, keep the base server URL
    base_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        base_url += f":{parsed.port}"

    # Try to extract project key from URL path
    project_key = ""
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    for i, part in enumerate(path_parts):
        if part.lower() in ("projects", "browse") and i + 1 < len(path_parts):
            project_key = path_parts[i + 1]
            break

    if not project_key:
        project_key = click.prompt("Jira project key (e.g., PROJ)")

    # Ask for optional JQL filter
    use_filter = click.confirm("Want to set a custom JQL filter?", default=False)
    jql_filter = ""
    if use_filter:
        default_jql = f"project = {project_key} ORDER BY updated DESC"
        jql_filter = click.prompt("JQL filter", default=default_jql)

    # Ask for a name
    name = click.prompt("Source name", default=project_key)

    source = SourceConfig(
        type="jira",
        url=base_url,
        project_key=project_key,
        filter=jql_filter,
        name=name,
    )

    # Check for duplicates
    for existing in config.sources:
        if existing.type == "jira" and existing.url == base_url and existing.project_key == project_key:
            console.print("[yellow]This Jira source is already configured.[/yellow]")
            return

    config.sources.append(source)
    config.save(project_root)

    # Create tickets subdirectory
    tickets_dir = project_root / "tickets" / name
    tickets_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[green]Added Jira source:[/green] {name} ({base_url}, project: {project_key})")


def cmd_add_github(url: str) -> None:
    """Add a GitHub repository as an issue source."""
    config = ProjectConfig.load()
    project_root = Path.cwd()

    # Parse repo from URL
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    # Remove .git suffix
    if path.endswith(".git"):
        path = path[:-4]

    parts = path.split("/")
    if len(parts) < 2:
        console.print("[red]Invalid GitHub URL. Expected: https://github.com/owner/repo[/red]")
        return

    repo_name = f"{parts[0]}/{parts[1]}"

    # Ask for a friendly name
    default_name = parts[1]
    name = click.prompt("Source name", default=default_name)

    # Ask for filter (issue state)
    issue_filter = click.prompt("Issue state filter", default="open", type=click.Choice(["open", "closed", "all"]))

    source = SourceConfig(
        type="github",
        url=url,
        project_key=repo_name,
        filter=issue_filter,
        name=name,
    )

    # Check for duplicates
    for existing in config.sources:
        if existing.type == "github" and existing.project_key == repo_name:
            console.print("[yellow]This GitHub source is already configured.[/yellow]")
            return

    config.sources.append(source)
    config.save(project_root)

    # Create tickets subdirectory
    tickets_dir = project_root / "tickets" / name
    tickets_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[green]Added GitHub source:[/green] {name} ({repo_name})")
