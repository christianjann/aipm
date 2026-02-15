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
@click.argument("period", default="week", type=click.Choice(["day", "week", "month", "year", "all"]))
@click.argument("user", default="all")
@click.option("--debug", "-d", is_flag=True, default=False, help="Print Copilot prompt and response for debugging")
def summary(period: str, user: str, debug: bool) -> None:
    """Generate a high-level project summary.

    PERIOD: day, week, month, year, or all (default: week)
    USER: 'all', 'me', or a specific username (default: all)
    """
    from aipm.commands.summary import cmd_summary

    cmd_summary(period=period, user=user, debug=debug)


@main.command()
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["md", "html", "all"]),
    default="all",
    help="Output format: md, html, or all (default: all)",
)
@click.option(
    "--date",
    is_flag=True,
    help="Include generation timestamp in reports",
)
def report(fmt: str, date: bool) -> None:
    """Generate a full set of reports under the configured output directory.

    Creates summaries for every period and user, plus a project plan.
    """
    from aipm.commands.report import cmd_report

    cmd_report(fmt=fmt, include_date=date)


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
@click.option("--horizon", "-h", default="", help="Time horizon: now, week, next-week, month, year, sometime")
@click.option("--due", default="", help="Due date (YYYY-MM-DD)")
@click.option("--repo", "-r", default="", help="Git URL or local path to check task completion against")
def ticket_add(
    title: str | None,
    status: str,
    priority: str,
    assignee: str,
    description: str,
    labels: str,
    horizon: str,
    due: str,
    repo: str,
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
        horizon=horizon,
        due=due,
        repo=repo,
    )


@ticket.command("list")
def ticket_list() -> None:
    """List all local tickets."""
    from aipm.commands.ticket import cmd_ticket_list

    cmd_ticket_list()


@ticket.command("upgrade")
def ticket_upgrade() -> None:
    """Upgrade existing tickets by filling in missing fields (horizon, due, etc.)."""
    from aipm.commands.ticket import cmd_ticket_upgrade

    cmd_ticket_upgrade()


@main.command()
@click.argument("ticket_key", required=False, default=None)
@click.option("--limit", "-n", default=0, help="Maximum number of tickets to check (0 = all)")
@click.option("--debug", "-d", is_flag=True, default=False, help="Print Copilot prompt and response for debugging")
def check(ticket_key: str | None, limit: int, debug: bool) -> None:
    """Check ticket completion against configured repos.

    Starts with the most urgent tickets. For each ticket with a repo configured,
    gathers git history / directory context and asks Copilot whether the task
    has been fulfilled.

    Optionally pass a TICKET_KEY (e.g. L-0001) to check a single ticket.
    """
    from aipm.commands.check import cmd_check

    cmd_check(ticket_key=ticket_key, limit=limit, debug=debug)


if __name__ == "__main__":
    main()
