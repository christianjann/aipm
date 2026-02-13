"""Tests for aipm report command."""

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
    assignee: str = "",
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
        assignee=assignee,
        source_type="local",
        horizon=horizon,
        due=due,
    )
    sanitized = title.lower().replace(" ", "_")[:30]
    (local_dir / f"{key}_{sanitized}.md").write_text(content)


# ---------------------------------------------------------------------------
# Basic invocation
# ---------------------------------------------------------------------------


def test_report_no_project(work_dir: Path, tmp_path: Path) -> None:
    """Report should error when no project is initialised."""
    import os

    os.chdir(tmp_path)  # a dir with no aipm.toml anywhere above
    runner = CliRunner()
    result = runner.invoke(main, ["report"])
    assert result.exit_code == 0
    assert "No AIPM project found" in result.output


def test_report_no_tickets(work_dir: Path) -> None:
    """Report should warn when there are no tickets."""
    _init_project(work_dir)
    runner = CliRunner()
    result = runner.invoke(main, ["report"])
    assert result.exit_code == 0
    assert "No tickets found" in result.output


def test_report_generates_all_by_default(work_dir: Path) -> None:
    """Default invocation generates both md and html files."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report"])
    assert result.exit_code == 0, result.output

    gen = work_dir / "generated"
    # Period summaries (4 periods x 2 formats)
    for period in ("day", "week", "month", "year"):
        assert (gen / f"summary_{period}.md").exists(), f"Missing summary_{period}.md"
        assert (gen / f"summary_{period}.html").exists(), f"Missing summary_{period}.html"

    # Plan
    assert (gen / "plan.md").exists()
    assert (gen / "plan.html").exists()

    assert "Generated" in result.output


def test_report_md_only(work_dir: Path) -> None:
    """--format md should only produce Markdown files."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "md"])
    assert result.exit_code == 0, result.output

    gen = work_dir / "generated"
    assert (gen / "summary_week.md").exists()
    assert not (gen / "summary_week.html").exists()
    assert (gen / "plan.md").exists()
    assert not (gen / "plan.html").exists()


def test_report_html_only(work_dir: Path) -> None:
    """--format html should only produce HTML files."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "html"])
    assert result.exit_code == 0, result.output

    gen = work_dir / "generated"
    assert not (gen / "summary_week.md").exists()
    assert (gen / "summary_week.html").exists()
    assert not (gen / "plan.md").exists()
    assert (gen / "plan.html").exists()


# ---------------------------------------------------------------------------
# Per-user reports
# ---------------------------------------------------------------------------


def test_report_per_user_summaries(work_dir: Path) -> None:
    """Week and month summaries should be generated per user."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Alice task", status="open", horizon="week", assignee="alice")
    _create_ticket(work_dir, "0002", "Bob task", status="open", horizon="month", assignee="bob")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "md"])
    assert result.exit_code == 0, result.output

    gen = work_dir / "generated"
    assert (gen / "summary_week_alice.md").exists()
    assert (gen / "summary_month_alice.md").exists()
    assert (gen / "summary_week_bob.md").exists()
    assert (gen / "summary_month_bob.md").exists()

    # Alice's week summary should mention her task
    alice_week = (gen / "summary_week_alice.md").read_text()
    assert "Alice task" in alice_week

    # Bob's week summary should not show Alice's task
    bob_week = (gen / "summary_week_bob.md").read_text()
    assert "Alice task" not in bob_week


# ---------------------------------------------------------------------------
# Plan content
# ---------------------------------------------------------------------------


def test_report_plan_content(work_dir: Path) -> None:
    """Plan markdown should contain a table with ticket data."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Build API", status="in progress", horizon="week", assignee="alice")
    _create_ticket(work_dir, "0002", "Write docs", status="done", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "md"])
    assert result.exit_code == 0, result.output

    plan = (work_dir / "generated" / "plan.md").read_text()
    assert "Build API" in plan
    assert "alice" in plan
    # Completed tickets should be shown
    assert "Write docs" in plan


def test_report_plan_html_structure(work_dir: Path) -> None:
    """Plan HTML should be a valid HTML document with a table."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Build API", status="open", horizon="now")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "html"])
    assert result.exit_code == 0, result.output

    plan_html = (work_dir / "generated" / "plan.html").read_text()
    assert "<!DOCTYPE html>" in plan_html
    assert "Build API" in plan_html
    assert "<table>" in plan_html


# ---------------------------------------------------------------------------
# Summary content checks
# ---------------------------------------------------------------------------


def test_report_summary_md_content(work_dir: Path) -> None:
    """Summary Markdown should include correct period and ticket info."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Urgent fix", status="open", horizon="now", priority="high")
    _create_ticket(work_dir, "0002", "Later task", status="open", horizon="year")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "md"])
    assert result.exit_code == 0, result.output

    day_md = (work_dir / "generated" / "summary_day.md").read_text()
    assert "Urgent fix" in day_md
    # Day should not include the year-horizon task
    assert "Later task" not in day_md

    year_md = (work_dir / "generated" / "summary_year.md").read_text()
    assert "Urgent fix" in year_md
    assert "Later task" in year_md


def test_report_summary_html_content(work_dir: Path) -> None:
    """Summary HTML should be a valid HTML document."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task A", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "html"])
    assert result.exit_code == 0, result.output

    week_html = (work_dir / "generated" / "summary_week.html").read_text()
    assert "<!DOCTYPE html>" in week_html
    assert "Task A" in week_html


def test_report_completed_tickets_strikethrough(work_dir: Path) -> None:
    """Completed tickets should appear with strikethrough in plan."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Done task", status="done", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "md"])
    assert result.exit_code == 0, result.output

    plan = (work_dir / "generated" / "plan.md").read_text()
    assert "~~" in plan and "Done task" in plan


# ---------------------------------------------------------------------------
# Index and navigation
# ---------------------------------------------------------------------------


def test_report_index_html_generated(work_dir: Path) -> None:
    """HTML reports should include an index.html with links to all reports."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", horizon="week", assignee="alice")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "html"])
    assert result.exit_code == 0, result.output

    gen = work_dir / "generated"
    index = gen / "index.html"
    assert index.exists()

    content = index.read_text()
    assert "<!DOCTYPE html>" in content
    assert "summary_week.html" in content
    assert "plan.html" in content
    assert "alice" in content.lower()


def test_report_html_pages_link_back_to_index(work_dir: Path) -> None:
    """Each generated HTML page should have a link back to index.html."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "html"])
    assert result.exit_code == 0, result.output

    gen = work_dir / "generated"
    for html_file in gen.glob("*.html"):
        if html_file.name == "index.html":
            continue
        content = html_file.read_text()
        assert 'href="index.html"' in content, f"{html_file.name} missing back link"


def test_report_md_only_no_index(work_dir: Path) -> None:
    """Markdown-only reports should not generate index.html."""
    _init_project(work_dir)
    _create_ticket(work_dir, "0001", "Task one", status="open", horizon="week")

    runner = CliRunner()
    result = runner.invoke(main, ["report", "-f", "md"])
    assert result.exit_code == 0, result.output

    assert not (work_dir / "generated" / "index.html").exists()
