"""aipm summary - Generate high-level project summaries."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from aipm.config import ProjectConfig, get_project_root

console = Console()


def _collect_all_tickets(project_root: Path) -> list[dict[str, str]]:
    """Read all ticket files and return parsed metadata."""
    tickets_dir = project_root / "tickets"
    if not tickets_dir.exists():
        return []

    tickets: list[dict[str, str]] = []
    for md_file in tickets_dir.rglob("*.md"):
        content = md_file.read_text()
        info = _parse_ticket(content, md_file)
        tickets.append(info)

    return tickets


def _parse_ticket(content: str, filepath: Path) -> dict[str, str]:
    """Parse ticket markdown to extract fields."""
    info: dict[str, str] = {"file": str(filepath)}
    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            info["title"] = line[2:].strip()
        if "| **" in line and "** |" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                field = parts[1].strip().strip("*").strip()
                value = parts[2].strip()
                info[field.lower()] = value
    return info


def _filter_by_user(tickets: list[dict[str, str]], user: str) -> list[dict[str, str]]:
    """Filter tickets by assignee."""
    if user == "all":
        return tickets
    return [t for t in tickets if t.get("assignee", "").lower() == user.lower()]


def _generate_summary_with_copilot(
    tickets: list[dict[str, str]],
    period: str,
    user: str,
    config: ProjectConfig,
    goals: str,
    milestones: str,
) -> str:
    """Generate summary using Copilot."""
    try:
        from github_copilot import Copilot

        # Build ticket info
        ticket_lines = []
        for t in tickets[:50]:
            title = t.get("title", "Unknown")
            status = t.get("status", "unknown")
            assignee = t.get("assignee", "Unassigned")
            priority = t.get("priority", "")
            ticket_lines.append(f"- [{status}] {title} (Assignee: {assignee}, Priority: {priority})")

        ticket_text = "\n".join(ticket_lines)

        copilot = Copilot()
        prompt = (
            f"You are an AI project manager for '{config.name}'. "
            f"Generate a {period}ly summary report. "
            f"User filter: {user}.\n\n"
            "Focus on:\n"
            "1. Key accomplishments in this period\n"
            "2. Current priorities and next tasks\n"
            "3. Progress toward goals\n"
            "4. Risks and blockers\n"
            "5. Recommended focus areas\n\n"
            f"## Goals\n{goals}\n\n"
            f"## Milestones\n{milestones}\n\n"
            f"## Tickets\n{ticket_text}"
        )

        response = copilot.chat(prompt)
        return response
    except Exception:
        return _generate_summary_fallback(tickets, period, user, config)


def _generate_summary_fallback(
    tickets: list[dict[str, str]],
    period: str,
    user: str,
    config: ProjectConfig,
) -> str:
    """Generate a summary without AI."""
    now = datetime.now()
    lines = [
        f"# {config.name} - {period.title()} Summary",
        "",
        f"_Generated: {now.strftime('%Y-%m-%d %H:%M')}_",
        f"_Filter: {user}_",
        "",
    ]

    # Group by status
    by_status: dict[str, list[dict[str, str]]] = {}
    for t in tickets:
        status = t.get("status", "unknown").lower()
        by_status.setdefault(status, []).append(t)

    total = len(tickets)
    lines.append(f"## Overview ({total} tickets)")
    lines.append("")

    for status, items in sorted(by_status.items()):
        lines.append(f"- **{status.title()}**: {len(items)}")
    lines.append("")

    # Active / in-progress items
    active_statuses = {"open", "in progress", "in review", "in development", "to do"}
    active = [t for t in tickets if t.get("status", "").lower() in active_statuses]

    if active:
        lines.append("## Active Tasks")
        lines.append("")

        # Group by priority
        hp_values = ("highest", "high", "critical", "urgent")
        high_priority = [t for t in active if t.get("priority", "").lower() in hp_values]
        normal = [t for t in active if t not in high_priority]

        if high_priority:
            lines.append("### High Priority")
            lines.append("")
            for t in high_priority:
                title = t.get("title", "Unknown")
                assignee = t.get("assignee", "Unassigned")
                lines.append(f"- **{title}** ({assignee})")
            lines.append("")

        if normal:
            lines.append("### Normal Priority")
            lines.append("")
            for t in normal[:15]:
                title = t.get("title", "Unknown")
                assignee = t.get("assignee", "Unassigned")
                lines.append(f"- {title} ({assignee})")
            if len(normal) > 15:
                lines.append(f"- _...and {len(normal) - 15} more_")
            lines.append("")

    # Completed items
    done_statuses = {"done", "closed", "resolved", "complete", "completed"}
    completed = [t for t in tickets if t.get("status", "").lower() in done_statuses]

    if completed:
        lines.append(f"## Completed ({len(completed)})")
        lines.append("")
        for t in completed[:10]:
            title = t.get("title", "Unknown")
            lines.append(f"- ~~{title}~~")
        if len(completed) > 10:
            lines.append(f"- _...and {len(completed) - 10} more_")
        lines.append("")

    # Next steps
    lines.append("## Recommended Next Steps")
    lines.append("")
    if high_priority:
        lines.append("1. Focus on high-priority items listed above")
    if active:
        lines.append(f"2. {len(active)} active tasks need attention")
    lines.append("3. Run `aipm sync` to get latest updates")
    lines.append("4. Run `aipm plan` to refresh milestones")
    lines.append("")

    return "\n".join(lines)


def cmd_summary(period: str = "week", user: str = "all") -> None:
    """Generate a high-level project summary."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    config = ProjectConfig.load(project_root)

    console.print(f"[bold]Generating {period} summary for {config.name}...[/bold]\n")

    # Collect data
    tickets = _collect_all_tickets(project_root)

    if user != "all":
        tickets = _filter_by_user(tickets, user)

    if not tickets:
        console.print("[yellow]No tickets found. Run 'aipm sync' first.[/yellow]")
        return

    # Read context
    goals = ""
    goals_path = project_root / "goals.md"
    if goals_path.exists():
        goals = goals_path.read_text()

    milestones = ""
    milestones_path = project_root / "milestones.md"
    if milestones_path.exists():
        milestones = milestones_path.read_text()

    summary = _generate_summary_with_copilot(tickets, period, user, config, goals, milestones)

    md = Markdown(summary)
    console.print(Panel(md, title=f"{period.title()} Summary", border_style="blue"))
