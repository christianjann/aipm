"""Tests for aipm ticket commands."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from aipm.cli import main


def _init_project(work_dir: Path) -> None:
    """Helper to initialize a project in work_dir."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="testproject\nA test project\n")


def test_ticket_add_creates_file(work_dir: Path) -> None:
    """Verify aipm ticket add creates a markdown file under tickets/local/."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ticket", "add"],
        input="My first ticket\nSome description\nmedium\nsometime\n\n\n\n",
    )

    assert result.exit_code == 0, result.output

    local_dir = work_dir / "tickets" / "local"
    assert local_dir.is_dir()

    md_files = list(local_dir.glob("*.md"))
    assert len(md_files) == 1
    assert md_files[0].name.startswith("0001_")


def test_ticket_add_sequential_numbering(work_dir: Path) -> None:
    """Verify tickets get sequential numbers."""
    _init_project(work_dir)

    runner = CliRunner()
    # Add first ticket
    runner.invoke(
        main,
        ["ticket", "add", "-t", "First ticket", "-p", "high"],
        input="\n\n",
    )
    # Add second ticket
    runner.invoke(
        main,
        ["ticket", "add", "-t", "Second ticket", "-p", "low"],
        input="\n\n",
    )

    local_dir = work_dir / "tickets" / "local"
    md_files = sorted(local_dir.glob("*.md"))
    assert len(md_files) == 2
    assert md_files[0].name.startswith("0001_")
    assert md_files[1].name.startswith("0002_")


def test_ticket_add_content(work_dir: Path) -> None:
    """Verify ticket file contains correct metadata."""
    _init_project(work_dir)

    runner = CliRunner()
    runner.invoke(
        main,
        ["ticket", "add", "-t", "Bug in login", "-p", "critical", "-a", "chris", "-d", "Login page crashes"],
    )

    local_dir = work_dir / "tickets" / "local"
    md_files = list(local_dir.glob("*.md"))
    assert len(md_files) == 1

    content = md_files[0].read_text()
    assert "Bug in login" in content
    assert "critical" in content
    assert "chris" in content
    assert "Login page crashes" in content
    assert "L-0001" in content
    assert "local" in content


def test_ticket_add_with_labels(work_dir: Path) -> None:
    """Verify labels are stored in the ticket."""
    _init_project(work_dir)

    runner = CliRunner()
    runner.invoke(
        main,
        ["ticket", "add", "-t", "Labeled ticket", "-p", "medium", "-l", "bug,frontend"],
    )

    local_dir = work_dir / "tickets" / "local"
    content = next(iter(local_dir.glob("*.md"))).read_text()
    assert "bug" in content
    assert "frontend" in content


def test_ticket_list_empty(work_dir: Path) -> None:
    """Verify ticket list shows message when empty."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["ticket", "list"])
    assert result.exit_code == 0
    assert "No local tickets" in result.output


def test_ticket_list_shows_tickets(work_dir: Path) -> None:
    """Verify ticket list displays created tickets."""
    _init_project(work_dir)

    runner = CliRunner()
    runner.invoke(main, ["ticket", "add", "-t", "My task", "-p", "high"])
    runner.invoke(main, ["ticket", "add", "-t", "Another task", "-p", "low"])

    result = runner.invoke(main, ["ticket", "list"])
    assert result.exit_code == 0
    assert "My task" in result.output
    assert "Another task" in result.output


def test_init_creates_local_dir(work_dir: Path) -> None:
    """Verify aipm init creates tickets/local/ directory."""
    _init_project(work_dir)
    assert (work_dir / "tickets" / "local").is_dir()


def test_ticket_add_with_horizon_flag(work_dir: Path) -> None:
    """Verify --horizon flag is stored in the ticket file."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ticket", "add", "-t", "Urgent fix", "--horizon", "now", "-p", "high"],
    )

    assert result.exit_code == 0, result.output
    assert "now" in result.output

    local_dir = work_dir / "tickets" / "local"
    content = next(iter(local_dir.glob("*.md"))).read_text()
    assert "now" in content
    assert "Horizon" in content


def test_ticket_add_with_due_date(work_dir: Path) -> None:
    """Verify --due flag is stored in the ticket file."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ticket", "add", "-t", "Deadline task", "--horizon", "week", "--due", "2025-07-15", "-p", "medium"],
    )

    assert result.exit_code == 0, result.output

    local_dir = work_dir / "tickets" / "local"
    content = next(iter(local_dir.glob("*.md"))).read_text()
    assert "2025-07-15" in content
    assert "Due" in content


def test_ticket_add_default_horizon_is_sometime(work_dir: Path) -> None:
    """When no horizon is specified non-interactively, default should be 'sometime'."""
    _init_project(work_dir)

    runner = CliRunner()
    runner.invoke(
        main,
        ["ticket", "add", "-t", "Low prio task", "-p", "low"],
    )

    local_dir = work_dir / "tickets" / "local"
    content = next(iter(local_dir.glob("*.md"))).read_text()
    assert "sometime" in content


def test_ticket_add_invalid_horizon(work_dir: Path) -> None:
    """Invalid horizon value should produce an error message."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ticket", "add", "-t", "Bad horizon", "--horizon", "tomorrow"],
    )

    assert result.exit_code == 0  # Doesn't crash
    assert "Invalid horizon" in result.output


def test_ticket_list_shows_horizon(work_dir: Path) -> None:
    """Verify ticket list table includes horizon column."""
    _init_project(work_dir)

    runner = CliRunner()
    runner.invoke(main, ["ticket", "add", "-t", "Task A", "--horizon", "week", "-p", "medium"])
    runner.invoke(main, ["ticket", "add", "-t", "Task B", "--horizon", "now", "-p", "high"])

    result = runner.invoke(main, ["ticket", "list"])
    assert result.exit_code == 0
    assert "Horizon" in result.output
    assert "week" in result.output
    assert "now" in result.output


def test_ticket_upgrade_adds_missing_horizon(work_dir: Path) -> None:
    """Upgrade should prompt for horizon on tickets that lack it."""
    _init_project(work_dir)

    # Create a ticket file without horizon field (old format)
    local_dir = work_dir / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# L-0001: Old ticket\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| **Status** | open |\n"
        "| **Priority** | medium |\n"
        "| **Source** | local |\n"
    )
    (local_dir / "0001_old_ticket.md").write_text(content)

    runner = CliRunner()
    # Answer: yes to update, "week" for horizon, empty for due, empty for assignee, empty for repo
    result = runner.invoke(main, ["ticket", "upgrade"], input="y\nweek\n\n\n\n")

    assert result.exit_code == 0, result.output
    assert "Updated" in result.output

    # Verify the file now has horizon
    updated = (local_dir / "0001_old_ticket.md").read_text()
    assert "Horizon" in updated
    assert "week" in updated


def test_ticket_upgrade_skips_complete_tickets(work_dir: Path) -> None:
    """Upgrade should skip tickets that already have all fields."""
    _init_project(work_dir)

    runner = CliRunner()
    # Create a ticket with all fields filled
    runner.invoke(
        main,
        ["ticket", "add", "-t", "Complete ticket", "--horizon", "now", "-p", "high", "-a", "alice"],
    )

    result = runner.invoke(main, ["ticket", "upgrade"])

    assert result.exit_code == 0, result.output
    assert "already complete" in result.output
    assert "0 upgraded" in result.output


def test_ticket_upgrade_skip_individual(work_dir: Path) -> None:
    """User can skip a ticket during upgrade."""
    _init_project(work_dir)

    local_dir = work_dir / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# L-0001: Skip me\n\n| Field | Value |\n|-------|-------|\n| **Status** | open |\n| **Source** | local |\n"
    )
    (local_dir / "0001_skip_me.md").write_text(content)

    runner = CliRunner()
    # Answer "n" to skip
    result = runner.invoke(main, ["ticket", "upgrade"], input="n\n")

    assert result.exit_code == 0, result.output
    assert "1 skipped" in result.output


def test_ticket_upgrade_no_tickets(work_dir: Path) -> None:
    """Upgrade on empty project should report no tickets."""
    _init_project(work_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["ticket", "upgrade"])

    assert result.exit_code == 0
    assert "No local tickets" in result.output
