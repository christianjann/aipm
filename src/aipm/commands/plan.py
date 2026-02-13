"""aipm plan - Update the project plan based on ticket status."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from aipm.config import ProjectConfig, get_project_root
from aipm.horizons import HORIZON_LABELS, HORIZONS, horizon_sort_key

console = Console()


def _collect_ticket_data(project_root: Path) -> list[dict[str, str]]:
    """Read all ticket files and return parsed metadata."""
    tickets_dir = project_root / "tickets"
    if not tickets_dir.exists():
        return []

    tickets: list[dict[str, str]] = []
    for md_file in tickets_dir.rglob("*.md"):
        content = md_file.read_text()
        ticket_info = _parse_ticket_md(content, md_file)
        tickets.append(ticket_info)

    return tickets


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
    tickets: list[dict[str, str]],
    current_milestones: str,
    current_goals: str,
    project_name: str,
) -> str:
    """Use Copilot to generate an updated plan."""
    try:
        from github_copilot import Copilot

        # Build ticket summary grouped by horizon
        by_horizon: dict[str, list[dict[str, str]]] = {}
        for t in tickets:
            h = t.get("horizon", "sometime")
            by_horizon.setdefault(h, []).append(t)

        ticket_summary = []
        for h in HORIZONS:
            if h not in by_horizon:
                continue
            label = HORIZON_LABELS.get(h, h.title())
            items = by_horizon[h]
            ticket_summary.append(f"\n### {label} ({len(items)})")
            for t in items[:20]:
                title = t.get("title", "Unknown")
                status = t.get("status", "unknown")
                assignee = t.get("assignee", "Unassigned")
                ticket_summary.append(f"- [{status}] {title} (Assignee: {assignee})")

        ticket_text = "\n".join(ticket_summary)

        copilot = Copilot()
        prompt = (
            f"You are an AI project manager for the project '{project_name}'. "
            "Based on the current ticket statuses and time horizons, update the milestones document. "
            "Focus on:\n"
            "1. Which milestones are on track, at risk, or completed\n"
            "2. Suggest timeline adjustments based on ticket progress\n"
            "3. Highlight blockers or concerns\n"
            "4. Keep the markdown format clean and consistent\n\n"
            f"## Current Milestones\n{current_milestones}\n\n"
            f"## Current Goals\n{current_goals}\n\n"
            f"## Ticket Status by Horizon\n{ticket_text}"
        )

        response = copilot.chat(prompt)
        return response
    except Exception:
        return _update_plan_fallback(tickets, project_name)


def _update_plan_fallback(
    tickets: list[dict[str, str]],
    project_name: str,
) -> str:
    """Fallback plan update without AI — grouped by time horizon."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {project_name} — Milestones",
        "",
        f"_Last updated: {now}_",
        "",
    ]

    # Status classification
    done_statuses = {"done", "closed", "resolved", "complete", "completed"}

    total = len(tickets)
    completed = [t for t in tickets if t.get("status", "").lower() in done_statuses]
    open_tickets = [t for t in tickets if t not in completed]

    lines.append(f"**Total:** {total} tickets · **Open:** {len(open_tickets)} · **Completed:** {len(completed)}")
    lines.append("")

    # Group open tickets by horizon
    if open_tickets:
        open_tickets.sort(key=lambda t: horizon_sort_key(t.get("horizon", "sometime")))

        by_horizon: dict[str, list[dict[str, str]]] = {}
        for t in open_tickets:
            h = t.get("horizon", "sometime").lower()
            by_horizon.setdefault(h, []).append(t)

        for h in HORIZONS:
            if h not in by_horizon:
                continue
            group = by_horizon[h]
            label = HORIZON_LABELS.get(h, h.title())
            lines.append(f"## {label} ({len(group)})")
            lines.append("")
            for t in group:
                title = t.get("title", "Unknown")
                assignee = t.get("assignee", "")
                status = t.get("status", "open")
                due = t.get("due", "")
                suffix_parts = []
                if assignee:
                    suffix_parts.append(assignee)
                if status.lower() not in {"open", "to do", "todo", "backlog", "new", "created"}:
                    suffix_parts.append(status)
                if due:
                    suffix_parts.append(f"due {due}")
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                lines.append(f"- [ ] {title}{suffix}")
            lines.append("")

    # Completed section
    if completed:
        lines.append(f"## Completed ({len(completed)})")
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
    tickets = _collect_ticket_data(project_root)

    if not tickets:
        console.print("[yellow]No tickets found. Run 'aipm sync' first.[/yellow]")
        return

    # Read existing files
    milestones_path = project_root / "milestones.md"
    goals_path = project_root / "goals.md"

    current_milestones = milestones_path.read_text() if milestones_path.exists() else ""
    current_goals = goals_path.read_text() if goals_path.exists() else ""

    # Generate updated plan
    updated_plan = _update_plan_with_copilot(
        tickets,
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
