"""Tests for aipm init command."""

from __future__ import annotations

from pathlib import Path

import toml
from click.testing import CliRunner

from aipm.cli import main
from aipm.config import CONFIG_FILENAME


def test_init_creates_folder_structure(work_dir: Path) -> None:
    """Verify aipm init creates all expected directories and files."""
    runner = CliRunner()
    result = runner.invoke(main, ["init"], input="testproject\nA test project\n")

    assert result.exit_code == 0, result.output

    # Directories
    assert (work_dir / "tickets").is_dir()
    assert (work_dir / "generated").is_dir()

    # Files
    assert (work_dir / CONFIG_FILENAME).is_file()
    assert (work_dir / "milestones.md").is_file()
    assert (work_dir / "goals.md").is_file()
    assert (work_dir / "README.md").is_file()
    assert (work_dir / "generated" / ".gitkeep").is_file()


def test_init_config_content(work_dir: Path) -> None:
    """Verify aipm.toml contains the project name and description."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="myproject\nMy description\n")

    config = toml.load(work_dir / CONFIG_FILENAME)
    assert config["project"]["name"] == "myproject"
    assert config["project"]["description"] == "My description"


def test_init_milestones_content(work_dir: Path) -> None:
    """Verify milestones.md contains the project name."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="myproject\nsome desc\n")

    content = (work_dir / "milestones.md").read_text()
    assert "myproject" in content
    assert "Milestones" in content


def test_init_goals_content(work_dir: Path) -> None:
    """Verify goals.md contains the project name."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="myproject\nsome desc\n")

    content = (work_dir / "goals.md").read_text()
    assert "myproject" in content
    assert "Goals" in content


def test_init_readme_content(work_dir: Path) -> None:
    """Verify README.md references the project structure."""
    runner = CliRunner()
    runner.invoke(main, ["init"], input="myproject\nMy cool project\n")

    content = (work_dir / "README.md").read_text()
    assert "myproject" in content
    assert "tickets/" in content
    assert "milestones.md" in content
    assert "goals.md" in content
    assert "generated/" in content


def test_init_does_not_overwrite_existing(work_dir: Path) -> None:
    """Verify aipm init asks before reinitializing."""
    runner = CliRunner()
    # First init
    runner.invoke(main, ["init"], input="proj1\ndesc1\n")

    # Second init — decline reinit
    result = runner.invoke(main, ["init"], input="n\n")
    assert result.exit_code == 0

    # Config should still have original values
    config = toml.load(work_dir / CONFIG_FILENAME)
    assert config["project"]["name"] == "proj1"


def test_config_copilot_model_roundtrip(work_dir: Path) -> None:
    """Verify copilot_model is saved to and loaded from aipm.toml."""
    from aipm.config import ProjectConfig

    config = ProjectConfig(name="test", description="d", copilot_model="claude-haiku-4.5")
    config.save(work_dir)

    loaded = ProjectConfig.load(work_dir)
    assert loaded.copilot_model == "claude-haiku-4.5"

    # Verify toml structure
    raw = toml.load(work_dir / CONFIG_FILENAME)
    assert raw["copilot"]["model"] == "claude-haiku-4.5"


def test_config_copilot_model_absent(work_dir: Path) -> None:
    """When no copilot section exists, copilot_model defaults to empty string."""
    from aipm.config import ProjectConfig

    config = ProjectConfig(name="test", description="d")
    config.save(work_dir)

    loaded = ProjectConfig.load(work_dir)
    assert loaded.copilot_model == ""

    # No copilot section in toml
    raw = toml.load(work_dir / CONFIG_FILENAME)
    assert "copilot" not in raw
