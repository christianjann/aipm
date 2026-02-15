from pathlib import Path

from click.testing import CliRunner

from aipm.cli import main


def _init_project(work_dir: Path) -> None:
    """Initialize a test project."""
    runner = CliRunner()
    result = runner.invoke(main, ["init"], input="test\n.\n")
    assert result.exit_code == 0


def test_upgrade_converts_to_yaml_and_preserves_description(work_dir: Path) -> None:
    """Upgrade should convert tickets to YAML frontmatter format and preserve description."""
    _init_project(work_dir)

    # Create a ticket with all required fields but in old table format
    local_dir = work_dir / "tickets" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# L-0005: Add debug mode for check\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| **Status** | completed |\n"
        "| **Priority** | medium |\n"
        "| **Horizon** | year | \n"
        "| **Source** | local |\n"
        "| **Repo** | . |\n"
        "\n"
        "## Description\n\n"
        "In debug mode show the full prompt sent to Copilot and the answer\n"
    )
    ticket_file = local_dir / "0005_add_debug_mode_for_check.md"
    ticket_file.write_text(content)

    runner = CliRunner()
    # Should upgrade even though all fields are present (because it's old format)
    # Provide input: y to upgrade, empty for assignee, empty for due
    result = runner.invoke(main, ["upgrade"], input="y\n\n\n")

    assert result.exit_code == 0, result.output

    # Check that the ticket was upgraded to YAML frontmatter format
    updated_content = ticket_file.read_text()
    assert updated_content.startswith("---"), "Ticket should start with YAML frontmatter"
    assert "status: completed" in updated_content
    assert "horizon: year" in updated_content
    assert "priority: medium" in updated_content
    assert "source: local" in updated_content
    assert "repo: ." in updated_content
    assert "## Description" in updated_content
    assert "In debug mode show the full prompt sent to Copilot and the answer" in updated_content
