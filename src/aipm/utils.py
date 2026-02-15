"""Utility helpers for AIPM."""

from __future__ import annotations

import asyncio
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
    summary: str = "",
    url: str = "",
    repo: str = "",
    source_type: str = "",
    horizon: str = "",
    due: str = "",
    extra_fields: dict[str, str] | None = None,
) -> str:
    """Format a ticket as a markdown file content with YAML front matter."""
    import frontmatter

    # Build front matter dict
    front_matter = {
        "key": key,
        "title": title,
        "status": status,
    }

    if source_type:
        front_matter["source"] = source_type
    if priority:
        front_matter["priority"] = priority
    if horizon:
        front_matter["horizon"] = horizon
    if assignee:
        front_matter["assignee"] = assignee
    if due:
        front_matter["due"] = due
    if repo:
        front_matter["repo"] = repo
    if url:
        front_matter["url"] = url
    if summary:
        front_matter["summary"] = summary
    if labels:
        front_matter["labels"] = labels
    if extra_fields:
        front_matter.update(extra_fields)

    # Prepare content
    content = ""
    if description:
        content = f"## Description\n\n{description}\n"

    # Use frontmatter to generate the full content
    post = frontmatter.Post(content, **front_matter)
    return frontmatter.dumps(post)


# Default model — cheapest Claude available on Copilot
COPILOT_DEFAULT_MODEL = "claude-haiku-4.5"


class ModelUnavailableError(RuntimeError):
    """Raised when the configured Copilot model fails and the user should pick another."""


def _get_configured_model() -> str:
    """Read the Copilot model from aipm.toml, or return the default."""
    from aipm.config import ProjectConfig, get_project_root

    project_root = get_project_root()
    if project_root is None:
        return COPILOT_DEFAULT_MODEL
    try:
        config = ProjectConfig.load(project_root)
        return config.copilot_model or COPILOT_DEFAULT_MODEL
    except FileNotFoundError:
        return COPILOT_DEFAULT_MODEL


def list_copilot_models() -> list[tuple[str, str]]:
    """Return available Copilot models as (id, name) pairs."""
    from copilot import CopilotClient

    async def _run() -> list[tuple[str, str]]:
        client = CopilotClient()
        await client.start()
        try:
            models = await client.list_models()
            return [(m.id, m.name) for m in models]
        finally:
            await client.stop()

    return asyncio.run(_run())


def select_copilot_model() -> str:
    """Interactively prompt the user to pick a Copilot model and save to config."""
    import click
    from rich.console import Console

    from aipm.config import ProjectConfig, get_project_root

    console = Console()
    console.print("[yellow]Configured Copilot model is not available. Fetching model list...[/yellow]")

    try:
        models = list_copilot_models()
    except Exception:
        console.print("[red]Could not fetch models from Copilot. Using default.[/red]")
        return COPILOT_DEFAULT_MODEL

    if not models:
        console.print("[red]No models available.[/red]")
        return COPILOT_DEFAULT_MODEL

    console.print("\n[bold]Available models:[/bold]")
    for i, (mid, mname) in enumerate(models, 1):
        console.print(f"  [cyan]{i}[/cyan]. {mid:40s} {mname}")

    choice = click.prompt(
        "\nSelect a model",
        type=click.IntRange(1, len(models)),
        default=next((i for i, (mid, _) in enumerate(models, 1) if "haiku" in mid), 1),
    )
    selected_id = models[choice - 1][0]
    console.print(f"  Selected: [green]{selected_id}[/green]")

    # Save to aipm.toml
    project_root = get_project_root()
    if project_root is not None:
        try:
            config = ProjectConfig.load(project_root)
            config.copilot_model = selected_id
            config.save(project_root)
            console.print("  Saved to [dim]aipm.toml[/dim]")
        except FileNotFoundError:
            pass

    return selected_id


def copilot_chat(prompt: str, *, timeout: float = 15.0, retries: int = 3, model: str | None = None) -> str:
    """Send a prompt to the Copilot SDK and return the response text.

    Uses the github-copilot-sdk (``copilot`` package) which provides an async
    client that spawns a local Copilot CLI server.  Reuses a single client
    across retries to avoid repeated server startup overhead.

    If the configured model is not available, raises ``ModelUnavailableError``
    so the caller can handle interactive model selection.

    Raises ``RuntimeError`` when the SDK is unavailable or all retries fail.
    """
    from copilot import CopilotClient

    effective_model = model or _get_configured_model()

    async def _run(use_model: str) -> str:
        last_err: Exception | None = None
        client = CopilotClient()
        await client.start()
        try:
            for _attempt in range(1, retries + 1):
                try:
                    session = await client.create_session({"model": use_model})
                    response = await session.send_and_wait({"prompt": prompt}, timeout=timeout)
                    await session.destroy()
                    if response and hasattr(response, "data"):
                        text = getattr(response.data, "content", None) or getattr(response.data, "message", None) or ""
                        if text:
                            return text
                    # Empty response — retry
                    last_err = RuntimeError("Copilot returned empty response")
                except TimeoutError as exc:
                    last_err = exc
                except Exception as exc:
                    # Non-timeout errors (e.g. invalid model) — don't retry
                    err_msg = str(exc).lower()
                    if "model" in err_msg or "not found" in err_msg or "invalid" in err_msg or "unavailable" in err_msg:
                        raise ModelUnavailableError(use_model) from exc
                    last_err = exc
        finally:
            await client.stop()
        msg = f"Copilot failed after {retries} attempts"
        raise RuntimeError(msg) from last_err

    try:
        return asyncio.run(_run(effective_model))
    except ModelUnavailableError:
        if model is not None:
            raise  # Caller explicitly requested a model, don't override
        raise
