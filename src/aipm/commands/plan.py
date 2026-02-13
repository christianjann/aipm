"""aipm plan - Update the project plan based on ticket status."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from aipm.config import ProjectConfig, get_project_root

console = Console()


def _collect_ticket_data(project_root: Path) -> dict[str, list[dict[str, str]]]:
    """Read all ticket files and group by status."""
    tickets_dir = project_root / "tickets"
    if not tickets_dir.exists():
        return {}

    by_status: dict[str, list[dict[str, str]]] = {}

    for md_file in tickets_dir.rglob("*.md"):
        content = md_file.read_text()
        ticket_info = _parse_ticket_md(content, md_file)
        status = ticket_info.get("status", "unknown").lower()
        by_status.setdefault(status, []).append(ticket_info)

    return by_status


def _parse_ticket_md(content: str, filepath: Path) -> dict[str, str]:
    """Parse a ticket markdown file to extract metadata."""
    info: dict[str, str] = {"file": str(filepath)}

    lines = content.split("\n")
    for line in lines:
        # Parse title from heading
        if line.startswith("# "):
            info["title"] = line[2:].strip()
        # Parse table fields
        if "| **" in line and "** |" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                field = parts[1].strip().strip("*").strip()
                value = parts[2].strip()
                info[field.lower()] = value

    return info


def _update_plan_with_copilot(
    tickets_by_status: dict[str, list[dict[str, str]]],
    current_milestones: str,
    current_goals: str,
    project_name: str,
) -> str:
    """Use Copilot to generate an updated plan."""
    try:
        from github_copilot import Copilot

        # Build ticket summary
        ticket_summary = []
        for status, tickets in sorted(tickets_by_status.items()):
            ticket_summary.append(f"\n### {status.title()} ({len(tickets)})")
            for t in tickets[:20]:  # Limit to prevent token overflow
                title = t.get("title", "Unknown")
                assignee = t.get("assignee", "Unassigned")
                priority = t.get("priority", "")
                ticket_summary.append(f"- {title} (Assignee: {assignee}, Priority: {priority})")

        ticket_text = "\n".join(ticket_summary)

        copilot = Copilot()
        prompt = (
            f"You are an AI project manager for the project '{project_name}'. "
            "Based on the current ticket statuses, update the milestones document. "
            "Focus on:\n"
            "1. Which milestones are on track, at risk, or completed\n"
            "2. Suggest timeline adjustments based on ticket progress\n"
            "3. Highlight blockers or concerns\n"
            "4. Keep the markdown format clean and consistent\n\n"
            f"## Current Milestones\n{current_milestones}\n\n"
            f"## Current Goals\n{current_goals}\n\n"
            f"## Ticket Status Summary\n{ticket_text}"
        )

        response = copilot.chat(prompt)
        return response
    except Exception:
        return _update_plan_fallback(tickets_by_status, project_name)


def _update_plan_fallback(
    tickets_by_status: dict[str, list[dict[str, str]]],
    project_name: str,
) -> str:
    """Fallback plan update without AI."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {project_name} - Milestones",
        "",
        f"_Last updated: {now}_",
        "",
    ]

    # Summary stats
    total = sum(len(v) for v in tickets_by_status.values())
    lines.append(f"**Total tickets:** {total}")
    for status, tickets in sorted(tickets_by_status.items()):
        lines.append(f"- {status.title()}: {len(tickets)}")
    lines.append("")

    # Group by status
    done_statuses = {"done", "closed", "resolved", "complete", "completed"}
    in_progress_statuses = {"in progress", "in review", "in development", "open"}

    completed = []
    in_progress = []
    remaining = []

    for status, tickets in tickets_by_status.items():
        if status in done_statuses:
            completed.extend(tickets)
        elif status in in_progress_statuses:
            in_progress.extend(tickets)
        else:
            remaining.extend(tickets)

    if in_progress:
        lines.append("## In Progress")
        lines.append("")
        for t in in_progress:
            title = t.get("title", "Unknown")
            assignee = t.get("assignee", "")
            suffix = f" ({assignee})" if assignee else ""
            lines.append(f"- [ ] {title}{suffix}")
        lines.append("")

    if remaining:
        lines.append("## Upcoming")
        lines.append("")
        for t in remaining:
            title = t.get("title", "Unknown")
            lines.append(f"- [ ] {title}")
        lines.append("")

    if completed:
        lines.append("## Completed")
        lines.append("")
        for t in completed:
            title = t.get("title", "Unknown")
            lines.append(f"- [x] {title}")
        lines.append("")

    return "\n".join(lines)


def cmd_plan() -> None:
    """Update the project plan based on current ticket status."""
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    config = ProjectConfig.load(project_root)

    console.print("[bold]Analyzing tickets and updating plan...[/bold]")

    # Collect ticket data
    tickets_by_status = _collect_ticket_data(project_root)

    if not tickets_by_status:
        console.print("[yellow]No tickets found. Run 'aipm sync' first.[/yellow]")
        return

    # Read existing files
    milestones_path = project_root / "milestones.md"
    goals_path = project_root / "goals.md"

    current_milestones = milestones_path.read_text() if milestones_path.exists() else ""
    current_goals = goals_path.read_text() if goals_path.exists() else ""

    # Generate updated plan
    updated_plan = _update_plan_with_copilot(
        tickets_by_status,
        current_milestones,
        current_goals,
        config.name,
    )

    # Write updated milestones
    milestones_path.write_text(updated_plan)

    console.print("\n[green]Updated milestones.md[/green]")
    console.print()

    md = Markdown(updated_plan)
    console.print(md)
