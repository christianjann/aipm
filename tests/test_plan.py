"""Tests for aipm plan command."""

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
    )
    sanitized = title.lower().replace(" ", "_")[:30]
    (local_dir / f"{key}_{sanitized}.md").write_text(content)


def test_plan_groups_by_horizon(work_dir: Path) -> None:
    """Plan should group tickets by time horizon."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Urgent fix", status="open", horizon="now")
    _create_ticket(work_dir, "0002", "Weekly task", status="open", horizon="week")
    _create_ticket(work_dir, "0003", "Someday", status="open", horizon="sometime")

    runner = CliRunner()
    result = runner.invoke(main, ["plan"])

    assert result.exit_code == 0, result.output

    # Check milestones.md was created
    milestones = (work_dir / "milestones.md").read_text()
    assert "Urgent fix" in milestones
    assert "Weekly task" in milestones
    assert "Someday" in milestones


def test_plan_completed_section(work_dir: Path) -> None:
    """Plan should show completed tickets separately."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Done task", status="done", horizon="week")
    _create_ticket(work_dir, "0002", "Open task", status="open", horizon="now")

    runner = CliRunner()
    result = runner.invoke(main, ["plan"])

    assert result.exit_code == 0, result.output

    milestones = (work_dir / "milestones.md").read_text()
    assert "Completed" in milestones
    assert "Done task" in milestones


def test_plan_empty_project(work_dir: Path) -> None:
    """Plan should handle no tickets gracefully."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["plan"])

    assert result.exit_code == 0
    assert "No tickets found" in result.output


def test_plan_writes_milestones_file(work_dir: Path) -> None:
    """Plan should write the milestones.md file."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "A task", status="open", horizon="month")

    runner = CliRunner()
    runner.invoke(main, ["plan"])

    milestones_path = work_dir / "milestones.md"
    assert milestones_path.exists()
    content = milestones_path.read_text()
    assert "testproject" in content
    assert "A task" in content
