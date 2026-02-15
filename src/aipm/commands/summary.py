"""aipm summary - Generate high-level project summaries."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from aipm.config import ProjectConfig, get_project_root
from aipm.horizons import HORIZON_LABELS, HORIZONS, horizon_sort_key, horizons_for_period

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

    # Check if it starts with front matter
    if lines and lines[0] == "---":
        # Parse YAML front matter
        front_matter_lines = []
        i = 1
        while i < len(lines) and lines[i] != "---":
            front_matter_lines.append(lines[i])
            i += 1

        if front_matter_lines:
            import yaml

            try:
                front_matter = yaml.safe_load("\n".join(front_matter_lines))
                if isinstance(front_matter, dict):
                    # Convert all values to strings, handle lists
                    for k, v in front_matter.items():
                        if isinstance(v, list):
                            info[k] = ", ".join(str(item) for item in v)
                        else:
                            info[k] = str(v) if v is not None else ""
                    return info
            except yaml.YAMLError:
                pass  # Fall back to old parsing

    # Fallback to old table parsing
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


def _filter_by_period(tickets: list[dict[str, str]], period: str) -> list[dict[str, str]]:
    """Filter tickets to only those whose horizon matches the requested period."""
    relevant = horizons_for_period(period)
    return [t for t in tickets if t.get("horizon", "sometime").lower() in relevant]


def _generate_summary_with_copilot(
    tickets: list[dict[str, str]],
    period: str,
    user: str,
    config: ProjectConfig,
    goals: str,
    milestones: str,
    *,
    debug: bool = False,
    offline: bool = False,
) -> tuple[str, bool]:
    """Generate summary using Copilot unless offline. Returns (text, used_copilot)."""
    if offline:
        return _generate_summary_fallback(tickets, period, user, config), False
    try:
        from aipm.utils import ModelUnavailableError, copilot_chat, select_copilot_model

        # Build ticket info
        ticket_lines = []
        for t in tickets[:50]:
            key = t.get("key", "")
            title = t.get("title", "Unknown")
            display_title = f"{key}: {title}" if key else title
            status = t.get("status", "unknown")
            assignee = t.get("assignee", "Unassigned")
            horizon = t.get("horizon", "sometime")
            ticket_lines.append(f"- [{status}] {display_title} (Assignee: {assignee}, Horizon: {horizon})")

        ticket_text = "\n".join(ticket_lines)

        prompt = (
            f"You are an AI project manager for '{config.name}'. "
            f"Generate a {period} summary report. "
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

        if debug:
            console.print(Panel(prompt, title="Copilot prompt", border_style="yellow"))

        with console.status("  Waiting for Copilot..."):
            result = copilot_chat(prompt)

        if not result or not result.strip():
            console.print("  [dim]Copilot returned empty response, using fallback[/dim]")
            return _generate_summary_fallback(tickets, period, user, config), False

        if debug:
            console.print(Panel(result, title="Copilot response", border_style="yellow"))

        return result, True
    except ModelUnavailableError:
        new_model = select_copilot_model()
        try:
            with console.status("  Waiting for Copilot..."):
                result = copilot_chat(prompt, model=new_model)
            if result and result.strip():
                if debug:
                    console.print(Panel(result, title="Copilot response", border_style="yellow"))
                return result, True
        except Exception:
            pass
        return _generate_summary_fallback(tickets, period, user, config), False
    except Exception:
        return _generate_summary_fallback(tickets, period, user, config), False


def _generate_summary_fallback(
    tickets: list[dict[str, str]],
    period: str,
    user: str,
    config: ProjectConfig,
) -> str:
    """Generate a summary without AI, grouped by time horizon."""
    now = datetime.now()
    lines = [
        f"# {config.name} — {period.title()} Summary",
        "",
        f"_Generated: {now.strftime('%Y-%m-%d %H:%M')}_",
        f"_Filter: {user} · Period: {period}_",
        "",
    ]

    # Filter tickets to the requested period
    relevant_horizons = horizons_for_period(period)
    period_tickets = [t for t in tickets if t.get("horizon", "sometime").lower() in relevant_horizons]

    # Status classification
    done_statuses = {"done", "closed", "resolved", "complete", "completed"}
    active_statuses = {"in progress", "in review", "in development", "active"}

    total = len(period_tickets)
    completed = [t for t in period_tickets if t.get("status", "").lower() in done_statuses]
    active = [t for t in period_tickets if t.get("status", "").lower() in active_statuses]
    remaining = [t for t in period_tickets if t not in completed and t not in active]

    lines.append(f"## Overview ({total} tickets in scope)")
    lines.append("")
    if active:
        lines.append(f"- **Active:** {len(active)}")
    if remaining:
        lines.append(f"- **Open:** {len(remaining)}")
    if completed:
        lines.append(f"- **Completed:** {len(completed)}")
    lines.append("")

    # Group non-completed tickets by horizon, then by status within each horizon
    open_tickets = active + remaining
    if open_tickets:
        # Sort by horizon urgency
        open_tickets.sort(key=lambda t: horizon_sort_key(t.get("horizon", "sometime")))

        by_horizon: dict[str, list[dict[str, str]]] = {}
        for t in open_tickets:
            h = t.get("horizon", "sometime").lower()
            by_horizon.setdefault(h, []).append(t)

        for h in HORIZONS:
            if h not in by_horizon or h not in relevant_horizons:
                continue
            group = by_horizon[h]
            label = HORIZON_LABELS.get(h, h.title())
            lines.append(f"## {label} ({len(group)})")
            lines.append("")

            # Sort by priority within horizon
            hp_values = ("highest", "high", "critical", "urgent")
            high = [t for t in group if t.get("priority", "").lower() in hp_values]
            normal = [t for t in group if t not in high]

            for t in high:
                key = t.get("key", "")
                title = t.get("title", "Unknown")
                display_title = f"{key}: {title}" if key else title
                assignee = t.get("assignee", "")
                status = t.get("status", "open")
                due = t.get("due", "")
                suffix_parts = []
                if assignee:
                    suffix_parts.append(assignee)
                if due:
                    suffix_parts.append(f"due {due}")
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                lines.append(f"- **⚡ {display_title}** [{status}]{suffix}")

            for t in normal:
                key = t.get("key", "")
                title = t.get("title", "Unknown")
                display_title = f"{key}: {title}" if key else title
                assignee = t.get("assignee", "")
                status = t.get("status", "open")
                due = t.get("due", "")
                suffix_parts = []
                if assignee:
                    suffix_parts.append(assignee)
                if due:
                    suffix_parts.append(f"due {due}")
                suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
                lines.append(f"- {display_title} [{status}]{suffix}")

            lines.append("")

    # Completed
    if completed:
        lines.append(f"## Completed ({len(completed)})")
        lines.append("")
        for t in completed[:10]:
            key = t.get("key", "")
            title = t.get("title", "Unknown")
            display_title = f"{key}: {title}" if key else title
            lines.append(f"- ~~{display_title}~~")
        if len(completed) > 10:
            lines.append(f"- _...and {len(completed) - 10} more_")
        lines.append("")

    # Tickets outside scope (only show count if period != "all")
    if period != "all":
        out_of_scope = [
            t for t in tickets if t not in period_tickets and t.get("status", "").lower() not in done_statuses
        ]
        if out_of_scope:
            lines.append(
                f"_({len(out_of_scope)} tickets in later horizons not shown"
                " — use `aipm summary all` to see everything)_"
            )
            lines.append("")

    # Next steps
    lines.append("## Recommended Next Steps")
    lines.append("")
    now_tickets = [t for t in open_tickets if t.get("horizon", "").lower() == "now"]
    if now_tickets:
        lines.append(f"1. **{len(now_tickets)} urgent ticket(s)** need immediate attention")
    if active:
        lines.append(f"2. {len(active)} task(s) currently in progress")
    lines.append("3. Run `aipm sync` to get latest updates")
    lines.append("4. Run `aipm plan` to refresh milestones")
    lines.append("")

    return "\n".join(lines)


def cmd_summary(period: str = "week", user: str = "all", *, debug: bool = False, offline: bool = False) -> None:
    """Generate a high-level project summary, offline disables Copilot."""
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

    summary_text, used_copilot = _generate_summary_with_copilot(
        tickets, period, user, config, goals, milestones, debug=debug, offline=offline
    )

    # Indicate mode used
    mode_note = f"Mode: {'Copilot' if used_copilot else 'Offline/Fallback'}"
    md = Markdown(summary_text + f"\n\n{mode_note}")
    console.print(Panel(md, title=f"{period.title()} Summary", border_style="blue"))
