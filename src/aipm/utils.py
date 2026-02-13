"""Utility helpers for AIPM."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def sanitize_name(name: str, max_length: int = 60) -> str:
    """Sanitize a ticket name for use as a filename.

    Converts to lowercase, replaces non-alphanumeric characters with underscores,
    and truncates to max_length.
    """
    # Replace non-alphanumeric with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    # Lowercase
    sanitized = sanitized.lower()
    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")
    return sanitized


def run_git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    cmd = ["git", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def git_stage_files(files: list[Path], cwd: Path | None = None) -> None:
    """Stage files with git add."""
    if not files:
        return
    str_files = [str(f) for f in files]
    run_git("add", *str_files, cwd=cwd)


def git_has_staged_changes(cwd: Path | None = None) -> bool:
    """Check if there are currently staged changes."""
    result = run_git("diff", "--cached", "--name-only", cwd=cwd)
    return bool(result.stdout.strip())


def git_staged_diff(cwd: Path | None = None) -> str:
    """Get the diff of staged changes."""
    result = run_git("diff", "--cached", cwd=cwd)
    return result.stdout


def git_commit(message: str, cwd: Path | None = None) -> None:
    """Create a git commit with the given message."""
    run_git("commit", "-m", message, cwd=cwd)


def format_markdown_ticket(
    *,
    key: str,
    title: str,
    status: str,
    assignee: str = "",
    priority: str = "",
    labels: list[str] | None = None,
    description: str = "",
    url: str = "",
    source_type: str = "",
    extra_fields: dict[str, str] | None = None,
) -> str:
    """Format a ticket as a markdown file content."""
    lines = [
        f"# {key}: {title}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Status** | {status} |",
    ]

    if assignee:
        lines.append(f"| **Assignee** | {assignee} |")
    if priority:
        lines.append(f"| **Priority** | {priority} |")
    if labels:
        lines.append(f"| **Labels** | {', '.join(labels)} |")
    if source_type:
        lines.append(f"| **Source** | {source_type} |")
    if url:
        lines.append(f"| **URL** | [{url}]({url}) |")

    if extra_fields:
        for field_name, field_value in extra_fields.items():
            lines.append(f"| **{field_name}** | {field_value} |")

    lines.append("")

    if description:
        lines.extend(["## Description", "", description, ""])

    return "\n".join(lines)
