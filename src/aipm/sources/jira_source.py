"""Jira issue source backend."""

from __future__ import annotations

from urllib.parse import urlparse

from jira import JIRA

from aipm.config import SourceConfig
from aipm.sources.base import IssueSource, Ticket


class JiraSource(IssueSource):
    """Jira issue source."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.client: JIRA | None = None

    def connect(self) -> None:
        """Connect to Jira using environment variables or token auth.

        Expects JIRA_TOKEN and optionally JIRA_EMAIL environment variables.
        """
        import os

        server = self.config.url
        token = os.environ.get("JIRA_TOKEN", "")
        email = os.environ.get("JIRA_EMAIL", "")

        if token and email:
            self.client = JIRA(server=server, basic_auth=(email, token))
        elif token:
            self.client = JIRA(server=server, token_auth=token)
        else:
            # Try without auth (for public instances)
            self.client = JIRA(server=server)

    def fetch_issues(self) -> list[Ticket]:
        """Fetch issues from Jira."""
        if self.client is None:
            self.connect()

        assert self.client is not None

        # Build JQL query
        if self.config.filter:
            jql = self.config.filter
        elif self.config.project_key:
            jql = f"project = {self.config.project_key} ORDER BY updated DESC"
        else:
            raise ValueError("Jira source needs either a project_key or filter configured.")

        issues = self.client.search_issues(jql, maxResults=500)
        tickets: list[Ticket] = []

        for issue in issues:
            labels = issue.fields.labels if hasattr(issue.fields, "labels") else []
            assignee = ""
            if hasattr(issue.fields, "assignee") and issue.fields.assignee:
                assignee = issue.fields.assignee.displayName

            priority = ""
            if hasattr(issue.fields, "priority") and issue.fields.priority:
                priority = issue.fields.priority.name

            description = ""
            if hasattr(issue.fields, "description") and issue.fields.description:
                description = issue.fields.description

            ticket = Ticket(
                key=str(issue.key),
                title=str(issue.fields.summary),
                status=str(issue.fields.status.name),
                assignee=assignee,
                priority=priority,
                labels=labels,
                description=description,
                url=f"{self.config.url}/browse/{issue.key}",
                source_type="jira",
                source_name=self.get_source_name(),
            )
            tickets.append(ticket)

        return tickets

    def get_source_name(self) -> str:
        """Return the source name (project key or parsed from URL)."""
        if self.config.name:
            return self.config.name
        if self.config.project_key:
            return self.config.project_key
        parsed = urlparse(self.config.url)
        return parsed.hostname or "jira"
