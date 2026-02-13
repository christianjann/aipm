"""Tests for aipm check command."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from aipm.cli import main
from aipm.commands.check import (
    CommitInfo,
    _analysis_suggests_done,
    _build_keywords,
    _filter_commits_by_message,
    _get_git_log,
    _parse_all_tickets,
    _parse_ticket_file,
    _resolve_repo_path,
    _update_ticket_status,
)
from aipm.utils import format_markdown_ticket


def _init_project(work_dir: Path) -> None:
    """Helper to initialize a project in work_dir."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="testproject\nA test project\n")


def _create_ticket(
    work_dir: Path,
    *,
    key: str = "L-0001",
    title: str = "Test task",
    status: str = "open",
    horizon: str = "now",
    priority: str = "high",
    description: str = "Implement the feature",
    repo: str = "",
) -> Path:
    """Create a ticket file directly and return its path."""
    local_dir = work_dir / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    num = key.split("-")[1]
    filepath = local_dir / f"{num}_test_task.md"
    content = format_markdown_ticket(
        key=key,
        title=title,
        status=status,
        priority=priority,
        description=description,
        horizon=horizon,
        repo=repo,
        source_type="local",
    )
    filepath.write_text(content)
    return filepath


def _init_git_repo(path: Path) -> None:
    """Initialize a bare git repo with a commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    readme = path / "README.md"
    readme.write_text("# Test project\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True)


# --- Unit tests ---


def test_parse_ticket_file(work_dir: Path) -> None:
    """Ticket file parsing extracts all fields including repo."""
    _init_project(work_dir)
    filepath = _create_ticket(work_dir, repo="/tmp/myrepo")
    info = _parse_ticket_file(filepath)

    assert info["key"] == "L-0001"
    assert info["title"] == "Test task"
    assert info["status"] == "open"
    assert info["horizon"] == "now"
    assert info["repo"] == "/tmp/myrepo"
    assert info["description"] == "Implement the feature"


def test_parse_all_tickets_sorted_by_horizon(work_dir: Path) -> None:
    """Tickets are returned sorted by horizon urgency."""
    _init_project(work_dir)
    local_dir = work_dir / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)

    # Create tickets with different horizons
    for i, horizon in enumerate(["sometime", "now", "week"], start=1):
        content = format_markdown_ticket(
            key=f"L-{i:04d}",
            title=f"Task {i}",
            status="open",
            priority="medium",
            horizon=horizon,
            source_type="local",
        )
        (local_dir / f"{i:04d}_task_{i}.md").write_text(content)

    tickets = _parse_all_tickets(work_dir)
    horizons = [t.get("horizon") for t in tickets]
    assert horizons == ["now", "week", "sometime"]


def test_context_from_local_git_repo(work_dir: Path) -> None:
    """_get_git_log returns commits from a git repo."""
    repo_dir = work_dir / "target_repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    commits = _get_git_log(repo_dir)
    assert len(commits) >= 1
    assert commits[0].message == "initial"
    assert len(commits[0].hash) == 40


def test_context_from_local_plain_dir(work_dir: Path) -> None:
    """Non-git directories return no commits."""
    plain_dir = work_dir / "plain"
    plain_dir.mkdir()
    (plain_dir / "app.py").write_text("print('hello')\n")

    commits = _get_git_log(plain_dir)
    assert commits == []


def test_resolve_repo_path_relative(work_dir: Path) -> None:
    """Relative paths are resolved against project root."""
    subdir = work_dir / "myrepo"
    subdir.mkdir()
    resolved = _resolve_repo_path("myrepo", work_dir)
    assert resolved == subdir


def test_resolve_repo_path_dot(work_dir: Path) -> None:
    """'.' resolves to project root."""
    resolved = _resolve_repo_path(".", work_dir)
    assert resolved == work_dir.resolve()


def test_build_keywords_from_ticket() -> None:
    """Keywords are extracted from title and description."""
    ticket = {"title": "Fix login crash", "description": "The login page crashes on submit", "key": "L-0001"}
    keywords = _build_keywords(ticket)
    assert "login" in keywords
    assert "crash" in keywords
    assert "page" in keywords
    assert "l-0001" in keywords
    # Stop words should be excluded
    assert "the" not in keywords


def test_filter_commits_by_message() -> None:
    """Commits are filtered by keyword match in message."""
    commits = [
        CommitInfo(hash="aaa", message="fix login crash on mobile"),
        CommitInfo(hash="bbb", message="update readme"),
        CommitInfo(hash="ccc", message="refactor auth login flow"),
    ]
    matching = _filter_commits_by_message(commits, ["login"])
    assert len(matching) == 2
    assert matching[0].hash == "aaa"
    assert matching[1].hash == "ccc"


def test_filter_commits_no_match() -> None:
    """No matches returns empty list."""
    commits = [
        CommitInfo(hash="aaa", message="update readme"),
    ]
    matching = _filter_commits_by_message(commits, ["deploy", "ci"])
    assert matching == []


# --- CLI integration tests ---


def test_check_no_project(work_dir: Path) -> None:
    """Check fails gracefully without a project."""
    runner = CliRunner()
    # Provide input in case the parent project's tickets trigger a close prompt.
    result = runner.invoke(main, ["check"], input="n\n" * 10)
    # Test runs inside tests/.tmp/ which may find the parent project.
    # Either way, it should not crash.
    assert result.exit_code == 0


def test_check_no_tickets(work_dir: Path) -> None:
    """Check reports when there are no tickets."""
    _init_project(work_dir)
    runner = CliRunner()
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 0
    assert "No tickets found" in result.output


def test_check_no_repos_configured(work_dir: Path) -> None:
    """Check reports when no tickets have repos set."""
    _init_project(work_dir)
    _create_ticket(work_dir, repo="")

    runner = CliRunner()
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 0
    assert "No tickets have a repo configured" in result.output


def test_check_skips_completed_tickets(work_dir: Path) -> None:
    """Completed tickets are skipped."""
    _init_project(work_dir)
    _create_ticket(work_dir, status="completed", repo="/tmp/somerepo")

    runner = CliRunner()
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 0
    assert "already completed" in result.output


def test_check_runs_against_local_repo(work_dir: Path) -> None:
    """Check gathers context from a local repo and produces output."""
    _init_project(work_dir)

    # Create a local git repo with a commit that matches the ticket
    target = work_dir / "target"
    target.mkdir()
    _init_git_repo(target)
    # Add a commit whose message matches the ticket description
    (target / "feature.py").write_text("# implement the feature\n")
    subprocess.run(["git", "add", "."], cwd=target, capture_output=True)
    subprocess.run(["git", "commit", "-m", "implement the feature"], cwd=target, capture_output=True)

    _create_ticket(work_dir, repo=str(target), description="Implement the feature")

    runner = CliRunner()
    result = runner.invoke(main, ["check"], input="n\n")
    assert result.exit_code == 0
    assert "L-0001" in result.output
    assert "Checking 1 ticket" in result.output
    # Should find the matching commit
    assert "relevant commit" in result.output
    assert "Close ticket" in result.output


def test_check_no_matching_commits(work_dir: Path) -> None:
    """When no commits match the ticket, report NOT STARTED."""
    _init_project(work_dir)

    target = work_dir / "target"
    target.mkdir()
    _init_git_repo(target)

    _create_ticket(work_dir, repo=str(target), description="Deploy to production")

    runner = CliRunner()
    result = runner.invoke(main, ["check"])
    assert result.exit_code == 0
    assert "No matching commits" in result.output or "NOT STARTED" in result.output


def test_check_specific_ticket(work_dir: Path) -> None:
    """Passing a ticket key checks only that ticket."""
    _init_project(work_dir)

    target = work_dir / "target"
    target.mkdir()
    _init_git_repo(target)

    _create_ticket(work_dir, repo=str(target))

    runner = CliRunner()
    result = runner.invoke(main, ["check", "L-0001"], input="n\n")
    assert result.exit_code == 0
    assert "L-0001" in result.output


def test_check_unknown_ticket_key(work_dir: Path) -> None:
    """Passing an unknown ticket key shows an error."""
    _init_project(work_dir)
    _create_ticket(work_dir, repo="/tmp/x")

    runner = CliRunner()
    result = runner.invoke(main, ["check", "L-9999"])
    assert result.exit_code == 0
    assert "not found" in result.output


def test_ticket_add_with_repo(work_dir: Path) -> None:
    """Verify aipm ticket add --repo stores the repo field."""
    _init_project(work_dir)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ticket", "add", "-t", "My task", "--repo", "/tmp/myproject", "-p", "high", "--horizon", "now"],
    )
    assert result.exit_code == 0, result.output

    local_dir = work_dir / "tickets" / "local"
    md_files = list(local_dir.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "/tmp/myproject" in content
    assert "**Repo**" in content


# --- Status detection and ticket update tests ---


def test_analysis_suggests_done_true() -> None:
    """Various DONE patterns are detected."""
    assert _analysis_suggests_done("**Status**: DONE\n**Confidence**: High")
    assert _analysis_suggests_done("1. **Status**: DONE")
    assert _analysis_suggests_done("Status: DONE")
    assert _analysis_suggests_done("**Status:** DONE")


def test_analysis_suggests_done_false() -> None:
    """Non-DONE analyses are not flagged."""
    assert not _analysis_suggests_done("**Status**: IN PROGRESS")
    assert not _analysis_suggests_done("**Status**: NOT STARTED")
    assert not _analysis_suggests_done("No relevant commits found.")
    assert not _analysis_suggests_done("")


def test_update_ticket_status(work_dir: Path) -> None:
    """_update_ticket_status rewrites the status field in place."""
    _init_project(work_dir)
    filepath = _create_ticket(work_dir, status="open")

    _update_ticket_status(filepath, "completed")

    content = filepath.read_text()
    assert "| **Status** | completed |" in content
    # Other fields should be preserved
    assert "**Horizon**" in content
    assert "**Priority**" in content


def test_check_prompts_to_close_done_ticket(work_dir: Path) -> None:
    """When relevant commits found, user is asked to close; answering yes updates the file."""
    _init_project(work_dir)

    target = work_dir / "target"
    target.mkdir()
    _init_git_repo(target)
    # Add a commit matching the ticket
    (target / "feature.py").write_text("# implement the feature\n")
    subprocess.run(["git", "add", "."], cwd=target, capture_output=True)
    subprocess.run(["git", "commit", "-m", "implement the feature"], cwd=target, capture_output=True)

    ticket_path = _create_ticket(work_dir, repo=str(target), description="Implement the feature")

    runner = CliRunner()
    # Answer 'y' to close the ticket
    result = runner.invoke(main, ["check"], input="y\n")
    assert result.exit_code == 0
    assert "Close ticket" in result.output
    assert "marked as completed" in result.output

    # Verify the ticket file was updated
    content = ticket_path.read_text()
    assert "| **Status** | completed |" in content


def test_check_decline_close_keeps_status(work_dir: Path) -> None:
    """When user declines to close, ticket status stays unchanged."""
    _init_project(work_dir)

    target = work_dir / "target"
    target.mkdir()
    _init_git_repo(target)
    (target / "feature.py").write_text("# implement the feature\n")
    subprocess.run(["git", "add", "."], cwd=target, capture_output=True)
    subprocess.run(["git", "commit", "-m", "implement the feature"], cwd=target, capture_output=True)

    ticket_path = _create_ticket(work_dir, repo=str(target), description="Implement the feature")

    runner = CliRunner()
    # Answer 'n' to decline closing
    result = runner.invoke(main, ["check"], input="n\n")
    assert result.exit_code == 0
    assert "Close ticket" in result.output
    assert "marked as completed" not in result.output

    # Verify the ticket file still has open status
    content = ticket_path.read_text()
    assert "| **Status** | open |" in content
