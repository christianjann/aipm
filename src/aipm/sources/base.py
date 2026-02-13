"""Base class for issue sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aipm.config import SourceConfig


@dataclass
class Ticket:
    """Represents a normalized issue/ticket from any source."""

    key: str
    title: str
    status: str
    assignee: str = ""
    priority: str = ""
    labels: list[str] | None = None
    description: str = ""
    url: str = ""
    repo: str = ""
    source_type: str = ""
    source_name: str = ""
    horizon: str = "sometime"
    due: str = ""
    extra_fields: dict[str, str] | None = None


class IssueSource(ABC):
    """Abstract base class for issue sources."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the issue source."""

    @abstractmethod
    def fetch_issues(self) -> list[Ticket]:
        """Fetch all relevant issues from the source."""

    @abstractmethod
    def get_source_name(self) -> str:
        """Return a human-readable name for this source."""
