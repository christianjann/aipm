"""Tests for aipm summary command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from aipm.cli import main
from aipm.utils import format_markdown_ticket


def _init_project(work_dir: Path) -> None:
    """Initialize a project in work_dir."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="testproject\nA test project\n")


def _create_ticket(
    work_dir: Path,
    key: str,
    title: str,
    status: str,
    priority: str = "medium",
    horizon: str = "sometime",
    due: str = "",
) -> None:
    """Create a ticket file directly for testing."""
    local_dir = work_dir / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    content = format_markdown_ticket(
        key=key,
        title=title,
        status=status,
        priority=priority,
        source_type="local",
        horizon=horizon,
        due=due,
    )
    sanitized = title.lower().replace(" ", "_")[:30]
    (local_dir / f"{key}_{sanitized}.md").write_text(content)


def test_summary_fallback_no_active_tickets(work_dir: Path) -> None:
    """Regression: summary crashed with UnboundLocalError when no active tickets exist."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", priority="low", horizon="week")
    _create_ticket(work_dir, "0002", "Task two", status="open", priority="medium", horizon="month")

    runner = CliRunner()
    result = runner.invoke(main, ["summary", "all"])

    assert result.exit_code == 0, result.output
    assert "This Week" in result.output or "Month" in result.output


def test_summary_with_active_tickets(work_dir: Path) -> None:
    """Summary should show tickets grouped by horizon."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Active task", status="in progress", priority="high", horizon="now")
    _create_ticket(work_dir, "0002", "Backlog task", status="open", priority="low", horizon="month")

    runner = CliRunner()
    result = runner.invoke(main, ["summary", "all"])

    assert result.exit_code == 0, result.output


def test_summary_empty_project(work_dir: Path) -> None:
    """Summary should handle a project with no tickets gracefully."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["summary"])

    assert result.exit_code == 0
    assert "No tickets found" in result.output


def test_summary_day_filters_to_now_horizon(work_dir: Path) -> None:
    """'summary day' should only show tickets with horizon='now'."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Urgent fix", status="open", horizon="now")
    _create_ticket(work_dir, "0002", "Weekly task", status="open", horizon="week")
    _create_ticket(work_dir, "0003", "Someday task", status="open", horizon="sometime")

    runner = CliRunner()
    result = runner.invoke(main, ["summary", "day"])

    assert result.exit_code == 0, result.output
    assert "Urgent fix" in result.output
    # Weekly and someday tasks should be excluded or shown as out of scope
    assert "not shown" in result.output or "later horizons" in result.output


def test_summary_week_includes_now_and_week(work_dir: Path) -> None:
    """'summary week' should show now + week horizon tickets."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Urgent fix", status="open", horizon="now")
    _create_ticket(work_dir, "0002", "Weekly task", status="open", horizon="week")
    _create_ticket(work_dir, "0003", "Monthly task", status="open", horizon="month")

    runner = CliRunner()
    result = runner.invoke(main, ["summary", "week"])

    assert result.exit_code == 0, result.output
    assert "Urgent fix" in result.output
    assert "Weekly task" in result.output


def test_summary_all_shows_everything(work_dir: Path) -> None:
    """'summary all' should show all tickets regardless of horizon."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Now task", status="open", horizon="now")
    _create_ticket(work_dir, "0002", "Sometime task", status="open", horizon="sometime")

    runner = CliRunner()
    result = runner.invoke(main, ["summary", "all"])

    assert result.exit_code == 0, result.output
    assert "Now task" in result.output
    assert "Sometime task" in result.output


def test_summary_completed_tickets_shown(work_dir: Path) -> None:
    """Completed tickets should appear in the Completed section."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Done task", status="done", horizon="week")
    _create_ticket(work_dir, "0002", "Open task", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["summary", "week"])

    assert result.exit_code == 0, result.output
    assert "Completed" in result.output
