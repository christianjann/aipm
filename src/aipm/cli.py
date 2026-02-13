"""AIPM CLI - The AI Project Manager command-line interface."""

from __future__ import annotations

import click
from rich.console import Console

from aipm import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="aipm")
def main() -> None:
    """AIPM - The AI Project Manager.

    Manage large projects distributed over multiple issue trackers and tools.
    """


@main.command()
def init() -> None:
    """Initialize a new AIPM project in the current directory."""
    from aipm.commands.init import cmd_init

    cmd_init()


@main.group()
def add() -> None:
    """Add an issue source to the project."""


@add.command("jira")
@click.argument("url")
def add_jira(url: str) -> None:
    """Add a Jira project as an issue source.

    URL should be the Jira server URL, e.g. https://mycompany.atlassian.net
    or https://jira.example.com/browse/PROJ
    """
    from aipm.commands.add import cmd_add_jira

    cmd_add_jira(url)


@add.command("github")
@click.argument("url")
def add_github(url: str) -> None:
    """Add a GitHub repository as an issue source.

    URL should be the GitHub repo URL, e.g. https://github.com/owner/repo
    """
    from aipm.commands.add import cmd_add_github

    cmd_add_github(url)


@main.command()
def sync() -> None:
    """Sync issues from all configured sources to the tickets directory."""
    from aipm.commands.sync import cmd_sync

    cmd_sync()


@main.command("diff")
def diff_cmd() -> None:
    """Summarize changes currently staged for commit."""
    from aipm.commands.diff import cmd_diff

    cmd_diff()


@main.command()
def plan() -> None:
    """Update the project plan based on current ticket status."""
    from aipm.commands.plan import cmd_plan

    cmd_plan()


@main.command()
@click.argument("period", default="week", type=click.Choice(["day", "week", "month", "year"]))
@click.argument("user", default="all")
def summary(period: str, user: str) -> None:
    """Generate a high-level project summary.

    PERIOD: day, week, month, or year (default: week)
    USER: 'all', 'me', or a specific username (default: all)
    """
    from aipm.commands.summary import cmd_summary

    cmd_summary(period=period, user=user)


@main.command()
def commit() -> None:
    """Commit the updated tickets and plan."""
    from aipm.commands.commit import cmd_commit

    cmd_commit()


if __name__ == "__main__":
    main()
