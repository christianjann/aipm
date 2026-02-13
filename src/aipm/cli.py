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


@main.group()
def ticket() -> None:
    """Manage local tickets."""


@ticket.command("add")
@click.option("--title", "-t", default=None, help="Ticket title")
@click.option("--status", "-s", default="open", help="Ticket status (default: open)")
@click.option("--priority", "-p", default="", help="Priority: critical, high, medium, low")
@click.option("--assignee", "-a", default="", help="Assignee")
@click.option("--description", "-d", default="", help="Description")
@click.option("--labels", "-l", default="", help="Comma-separated labels")
def ticket_add(
    title: str | None,
    status: str,
    priority: str,
    assignee: str,
    description: str,
    labels: str,
) -> None:
    """Create a new local ticket."""
    from aipm.commands.ticket import cmd_ticket_add

    cmd_ticket_add(
        title=title,
        status=status,
        priority=priority,
        assignee=assignee,
        description=description,
        labels=labels,
    )


@ticket.command("list")
def ticket_list() -> None:
    """List all local tickets."""
    from aipm.commands.ticket import cmd_ticket_list

    cmd_ticket_list()


if __name__ == "__main__":
    main()
