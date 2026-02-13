"""GitHub issue source backend."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from github import Github

from aipm.config import SourceConfig
from aipm.sources.base import IssueSource, Ticket


class GitHubSource(IssueSource):
    """GitHub issue source."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.client: Github | None = None
        self._repo_name: str = ""

    def connect(self) -> None:
        """Connect to GitHub using GITHUB_TOKEN environment variable."""
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            self.client = Github(token)
        else:
            self.client = Github()

        # Parse repo from URL
        self._repo_name = self._parse_repo_from_url(self.config.url)

    @staticmethod
    def _parse_repo_from_url(url: str) -> str:
        """Extract owner/repo from a GitHub URL."""
        # Handle URLs like https://github.com/owner/repo
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        # Remove .git suffix if present
        path = re.sub(r"\.git$", "", path)
        # Take first two path components (owner/repo)
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return path

    def fetch_issues(self) -> list[Ticket]:
        """Fetch issues from GitHub."""
        if self.client is None:
            self.connect()

        assert self.client is not None

        repo = self.client.get_repo(self._repo_name)

        # Fetch open issues (includes PRs on GitHub)
        state = "open"
        if self.config.filter:
            state = self.config.filter

        gh_issues = repo.get_issues(state=state)
        tickets: list[Ticket] = []

        for issue in gh_issues:
            # Skip pull requests
            if issue.pull_request is not None:
                continue

            labels = [label.name for label in issue.labels]
            assignee = ""
            if issue.assignee:
                assignee = issue.assignee.login

            ticket = Ticket(
                key=f"#{issue.number}",
                title=issue.title,
                status=issue.state,
                assignee=assignee,
                priority="",
                labels=labels,
                description=issue.body or "",
                url=issue.html_url,
                source_type="github",
                source_name=self.get_source_name(),
            )
            tickets.append(ticket)

        return tickets

    def get_source_name(self) -> str:
        """Return the source name."""
        if self.config.name:
            return self.config.name
        return self._repo_name or self._parse_repo_from_url(self.config.url)
