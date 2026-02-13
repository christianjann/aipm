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
        input="My first ticket\nSome description\nmedium\n\n",
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
