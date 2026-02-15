"""Configuration management for AIPM projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import toml

CONFIG_FILENAME = "aipm.toml"


@dataclass
class SourceConfig:
    """Configuration for a single issue source (Jira or GitHub)."""

    type: str  # "jira" or "github"
    url: str
    project_key: str = ""
    filter: str = ""
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceConfig:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProjectConfig:
    """AIPM project configuration stored in aipm.toml."""

    name: str = ""
    description: str = ""
    copilot_model: str = ""
    output_dir: str = "generated"
    sources: list[SourceConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "project": {
                "name": self.name,
                "description": self.description,
                "output_dir": self.output_dir,
            },
            "sources": [s.to_dict() for s in self.sources],
        }
        if self.copilot_model:
            d["copilot"] = {"model": self.copilot_model}
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectConfig:
        project = data.get("project", {})
        sources_data = data.get("sources", [])
        sources = [SourceConfig.from_dict(s) for s in sources_data]
        copilot = data.get("copilot", {})
        return cls(
            name=project.get("name", ""),
            description=project.get("description", ""),
            output_dir=project.get("output_dir", "generated"),
            copilot_model=copilot.get("model", ""),
            sources=sources,
        )

    def save(self, path: Path) -> None:
        """Save configuration to aipm.toml."""
        config_path = path / CONFIG_FILENAME
        with open(config_path, "w") as f:
            toml.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: Path | None = None) -> ProjectConfig:
        """Load configuration from aipm.toml, searching upward from path."""
        if path is None:
            path = Path.cwd()

        config_path = find_config(path)
        if config_path is None:
            raise FileNotFoundError(
                f"No {CONFIG_FILENAME} found in {path} or any parent directory. "
                "Run 'aipm init' to create a new project."
            )

        with open(config_path) as f:
            data = toml.load(f)

        config = cls.from_dict(data)
        return config

    @classmethod
    def load_from(cls, config_path: Path) -> ProjectConfig:
        """Load configuration from a specific aipm.toml file."""
        with open(config_path) as f:
            data = toml.load(f)
        return cls.from_dict(data)


def find_config(start: Path | None = None) -> Path | None:
    """Find aipm.toml by searching upward from start directory."""
    if start is None:
        start = Path.cwd()

    current = start.resolve()
    while True:
        config_path = current / CONFIG_FILENAME
        if config_path.exists():
            return config_path
        parent = current.parent
        if parent == current:
            return None
        current = parent


def get_project_root(start: Path | None = None) -> Path | None:
    """Find the project root (directory containing aipm.toml)."""
    config_path = find_config(start)
    if config_path is not None:
        return config_path.parent
    return None
