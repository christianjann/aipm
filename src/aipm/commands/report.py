"""aipm report - Generate a full set of project reports under the configured output directory."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from rich.console import Console

from aipm.config import ProjectConfig, get_project_root
from aipm.horizons import HORIZON_LABELS, HORIZONS, horizon_sort_key, horizons_for_period

console = Console()

# ---------------------------------------------------------------------------
# Ticket collection (shared helpers)
# ---------------------------------------------------------------------------


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
    for line in content.split("\n"):
        if line.startswith("# "):
            info["title"] = line[2:].strip()
        if "| **" in line and "** |" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                field = parts[1].strip().strip("*").strip()
                value = parts[2].strip()
                info[field.lower()] = value
    return info


def _unique_assignees(tickets: list[dict[str, str]]) -> list[str]:
    """Return sorted list of unique non-empty assignees."""
    assignees: set[str] = set()
    for t in tickets:
        a = t.get("assignee", "").strip()
        if a:
            assignees.add(a)
    return sorted(assignees)


# ---------------------------------------------------------------------------
# Markdown summary generation (offline, no AI)
# ---------------------------------------------------------------------------

_DONE_STATUSES = frozenset({"done", "closed", "resolved", "complete", "completed"})
_ACTIVE_STATUSES = frozenset({"in progress", "in review", "in development", "active"})


def _generate_summary_md(
    tickets: list[dict[str, str]],
    period: str,
    user: str,
    config: ProjectConfig,
    include_date: bool = False,
) -> str:
    """Generate a Markdown summary for *period* / *user*."""
    now = datetime.now()
    relevant = horizons_for_period(period)
    filtered = [t for t in tickets if t.get("horizon", "sometime").lower() in relevant]
    if user != "all":
        filtered = [t for t in filtered if t.get("assignee", "").lower() == user.lower()]

    completed = [t for t in filtered if t.get("status", "").lower() in _DONE_STATUSES]
    active = [t for t in filtered if t.get("status", "").lower() in _ACTIVE_STATUSES]
    remaining = [t for t in filtered if t not in completed and t not in active]

    user_label = user if user != "all" else "all users"
    lines = [
        f"# {config.name} — {period.title()} Summary",
        "",
    ]
    if include_date:
        lines.append(f"_Generated: {now.strftime('%Y-%m-%d %H:%M')}_  ")
    lines.append(f"_Filter: {user_label} · Period: {period}_")
    lines.append("")
    lines.append(f"## Overview ({len(filtered)} tickets)")
    lines.append("")
    if active:
        lines.append(f"- **Active:** {len(active)}")
    if remaining:
        lines.append(f"- **Open:** {len(remaining)}")
    if completed:
        lines.append(f"- **Completed:** {len(completed)}")
    lines.append("")

    open_tickets = active + remaining
    if open_tickets:
        open_tickets.sort(key=lambda t: horizon_sort_key(t.get("horizon", "sometime")))
        by_horizon: dict[str, list[dict[str, str]]] = {}
        for t in open_tickets:
            by_horizon.setdefault(t.get("horizon", "sometime").lower(), []).append(t)

        for h in HORIZONS:
            if h not in by_horizon or h not in relevant:
                continue
            group = by_horizon[h]
            label = HORIZON_LABELS.get(h, h.title())
            lines.append(f"## {label} ({len(group)})")
            lines.append("")
            hp = ("highest", "high", "critical", "urgent")
            high = [t for t in group if t.get("priority", "").lower() in hp]
            normal = [t for t in group if t not in high]
            for t in high:
                lines.append(_ticket_line(t, bold=True))
            for t in normal:
                lines.append(_ticket_line(t))
            lines.append("")

    if completed:
        lines.append(f"## Completed ({len(completed)})")
        lines.append("")
        for t in completed[:15]:
            lines.append(f"- ~~{t.get('title', '?')}~~")
        if len(completed) > 15:
            lines.append(f"- _...and {len(completed) - 15} more_")
        lines.append("")

    return "\n".join(lines)


def _ticket_line(t: dict[str, str], *, bold: bool = False) -> str:
    title = t.get("title", "?")
    assignee = t.get("assignee", "")
    status = t.get("status", "open")
    due = t.get("due", "")
    parts: list[str] = []
    if assignee:
        parts.append(assignee)
    if due:
        parts.append(f"due {due}")
    suffix = f" ({', '.join(parts)})" if parts else ""
    prefix = "**⚡ " if bold else ""
    end = f"** [{status}]" if bold else f" [{status}]"
    return f"- {prefix}{title}{end}{suffix}"


# ---------------------------------------------------------------------------
# Project plan (Markdown + HTML)
# ---------------------------------------------------------------------------


def _generate_plan_md(tickets: list[dict[str, str]], config: ProjectConfig, include_date: bool = False) -> str:
    """Generate a project plan in Markdown grouped by horizon."""
    now = datetime.now()
    lines = [
        f"# {config.name} — Project Plan",
        "",
    ]
    if include_date:
        lines.append(f"_Generated: {now.strftime('%Y-%m-%d %H:%M')}_")
    lines.extend(
        [
            "",
            "| Ticket | Assignee | Status | Horizon | Due |",
            "|--------|----------|--------|---------|-----|",
        ]
    )

    open_tickets = [t for t in tickets if t.get("status", "").lower() not in _DONE_STATUSES]
    open_tickets.sort(key=lambda t: horizon_sort_key(t.get("horizon", "sometime")))

    for t in open_tickets:
        title = t.get("title", "?")
        assignee = t.get("assignee", "")
        status = t.get("status", "open")
        horizon = t.get("horizon", "sometime")
        due = t.get("due", "")
        lines.append(f"| {title} | {assignee} | {status} | {horizon} | {due} |")

    lines.append("")

    # Completed at the end
    done = [t for t in tickets if t.get("status", "").lower() in _DONE_STATUSES]
    if done:
        lines.append(f"### Completed ({len(done)})")
        lines.append("")
        for t in done:
            lines.append(f"- ~~{t.get('title', '?')}~~")
        lines.append("")

    return "\n".join(lines)


def _generate_plan_html(tickets: list[dict[str, str]], config: ProjectConfig, include_date: bool = False) -> str:
    """Generate a project plan in HTML with coloured horizon bars."""
    now = datetime.now()
    _esc = html.escape

    horizon_colors: dict[str, str] = {
        "now": "#e74c3c",
        "week": "#e67e22",
        "next-week": "#f1c40f",
        "month": "#2ecc71",
        "year": "#3498db",
        "sometime": "#95a5a6",
    }

    open_tickets = [t for t in tickets if t.get("status", "").lower() not in _DONE_STATUSES]
    open_tickets.sort(key=lambda t: horizon_sort_key(t.get("horizon", "sometime")))
    done = [t for t in tickets if t.get("status", "").lower() in _DONE_STATUSES]

    # Group by horizon for bar width proportions
    max_bar = 100

    rows: list[str] = []
    for t in open_tickets:
        title = _esc(t.get("title", "?"))
        assignee = _esc(t.get("assignee", ""))
        status = _esc(t.get("status", "open"))
        horizon = t.get("horizon", "sometime").lower()
        due = _esc(t.get("due", ""))
        color = horizon_colors.get(horizon, "#95a5a6")
        label = HORIZON_LABELS.get(horizon, horizon.title())
        # Bar width: more urgent = wider bar
        idx = list(HORIZONS).index(horizon) if horizon in HORIZONS else len(HORIZONS)
        bar_pct = max(15, max_bar - idx * 15)
        rows.append(
            f"<tr>"
            f'<td class="title">{title}</td>'
            f"<td>{assignee}</td>"
            f"<td>{status}</td>"
            f"<td>{due}</td>"
            f'<td><div class="bar" style="width:{bar_pct}%;background:{color};">{_esc(label)}</div></td>'
            f"</tr>"
        )

    done_rows = ""
    if done:
        done_items = "\n".join(f"<li><s>{_esc(t.get('title', '?'))}</s></li>" for t in done)
        done_rows = f'<h3>Completed ({len(done)})</h3><ul class="done">{done_items}</ul>'

    nav_links = ['<a href="index.html">&larr; Back to index</a>']
    if config.url:
        nav_links.append(f'<a href="{_esc(config.url)}">&larr; Back to {config.name}</a>')
    nav = " | ".join(nav_links)

    open_count = len(open_tickets)
    done_count = len(done)
    generated_str = now.strftime("%Y-%m-%d %H:%M") if include_date else ""
    meta_parts = []
    if generated_str:
        meta_parts.append(f"Generated: {generated_str}")
    meta_parts.append(f"{open_count} open")
    meta_parts.append(f"{done_count} completed")
    meta = " · ".join(meta_parts)

    return _HTML_TEMPLATE.format(
        title=_esc(config.name),
        nav=nav,
        meta=meta,
        rows="\n".join(rows),
        done_section=done_rows,
    )


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Project Plan</title>
<style>
  :root {{ --bg: #1e1e2e; --fg: #cdd6f4; --surface: #313244; --border: #45475a; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 2rem; }}
  h1 {{ margin-bottom: .25rem; }}
  .meta {{ color: #a6adc8; margin-bottom: 1.5rem; font-size: .9rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
  th, td {{ padding: .5rem .75rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--surface); font-weight: 600; position: sticky; top: 0; }}
  .title {{ font-weight: 500; max-width: 320px; }}
  .bar {{ padding: 4px 8px; border-radius: 4px; color: #fff; font-size: .8rem;
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .done {{ list-style: none; columns: 2; }}
  .done li {{ padding: 2px 0; color: #a6adc8; }}
  h3 {{ margin: 1rem 0 .5rem; }}
  .nav {{ margin-bottom: 1rem; }}
  .nav a {{ color: #89b4fa; text-decoration: none; font-size: .9rem; }}
  .nav a:hover {{ text-decoration: underline; }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg: #eff1f5; --fg: #4c4f69; --surface: #e6e9ef; --border: #ccd0da; }}
    .done li {{ color: #7c7f93; }}
    .nav a {{ color: #1e66f5; }}
  }}
</style>
</head>
<body>
<p class="nav">{nav}</p>
<h1>{title} — Project Plan</h1>
<p class="meta">{meta}</p>
<table>
<thead><tr><th>Ticket</th><th>Assignee</th><th>Status</th><th>Due</th><th>Horizon</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
{done_section}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTML summary wrapper
# ---------------------------------------------------------------------------


def _md_to_html(md_text: str, title: str, config: ProjectConfig) -> str:
    """Convert a Markdown summary to a styled HTML page (simple converter)."""
    _esc = html.escape
    body_lines: list[str] = []
    in_list = False

    for line in md_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append("")
            continue

        if stripped.startswith("# "):
            body_lines.append(f"<h1>{_esc(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            body_lines.append(f"<h2>{_esc(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            body_lines.append(f"<h3>{_esc(stripped[4:])}</h3>")
        elif stripped.startswith("_") and stripped.endswith("_"):
            body_lines.append(f'<p class="meta">{_esc(stripped.strip("_"))}</p>')
        elif stripped.startswith("- "):
            if not in_list:
                body_lines.append("<ul>")
                in_list = True
            content = stripped[2:]
            # Handle ~~strikethrough~~
            if content.startswith("~~") and content.endswith("~~"):
                content = f"<s>{_esc(content[2:-2])}</s>"
            elif content.startswith("**") and "**" in content[2:]:
                content = _esc(content).replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            else:
                content = _esc(content)
            body_lines.append(f"<li>{content}</li>")
        elif stripped.startswith("|") and stripped.endswith("|"):
            # Skip raw markdown tables (plan has its own HTML)
            body_lines.append(f"<p>{_esc(stripped)}</p>")
        else:
            body_lines.append(f"<p>{_esc(stripped)}</p>")

    if in_list:
        body_lines.append("</ul>")

    body_html = "\n".join(body_lines)
    nav_links = ['<a href="index.html">&larr; Back to index</a>']
    if config.url:
        nav_links.append(f'<a href="{_esc(config.url)}">&larr; Back to {config.name}</a>')
    nav = " | ".join(nav_links)
    return _SUMMARY_HTML_TEMPLATE.format(title=_esc(title), nav=nav, body=body_html)


_SUMMARY_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg: #1e1e2e; --fg: #cdd6f4; --surface: #313244; --border: #45475a; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg);
          padding: 2rem; max-width: 900px; margin: 0 auto; line-height: 1.6; }}
  h1 {{ margin-bottom: .25rem; }}
  h2 {{ margin-top: 1.5rem; margin-bottom: .5rem; border-bottom: 1px solid var(--border); padding-bottom: .25rem; }}
  h3 {{ margin-top: 1rem; }}
  .meta {{ color: #a6adc8; font-size: .9rem; margin-bottom: .5rem; }}
  ul {{ padding-left: 1.5rem; margin: .5rem 0; }}
  li {{ margin: .25rem 0; }}
  s {{ color: #a6adc8; }}
  strong {{ color: #fab387; }}
  p {{ margin: .25rem 0; }}
  .nav {{ margin-bottom: 1rem; }}
  .nav a {{ color: #89b4fa; text-decoration: none; font-size: .9rem; }}
  .nav a:hover {{ text-decoration: underline; }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg: #eff1f5; --fg: #4c4f69; --surface: #e6e9ef; --border: #ccd0da; }}
    s {{ color: #7c7f93; }}
    strong {{ color: #d20f39; }}
    .nav a {{ color: #1e66f5; }}
  }}
</style>
</head>
<body>
<p class="nav">{nav}</p>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Report generation orchestrator
# ---------------------------------------------------------------------------

SUMMARY_PERIODS = ("day", "week", "month", "year")
PER_USER_PERIODS = ("week", "month")


def _generate_index_html(
    config: ProjectConfig,
    html_files: list[tuple[str, str]],
    include_date: bool = False,
) -> str:
    """Generate an index.html that links to all generated HTML reports.

    *html_files* is a list of ``(filename, label)`` pairs.
    """
    _esc = html.escape
    now = datetime.now()

    summary_links: list[str] = []
    user_links: list[str] = []
    plan_links: list[str] = []

    for fname, label in html_files:
        link = f'<li><a href="{_esc(fname)}">{_esc(label)}</a></li>'
        if fname.startswith("summary_") and fname.count("_") == 1 + fname.replace(".html", "").count("_") - 1:
            # Heuristic: per-user files have 3+ parts (summary_week_alice.html)
            parts = fname.replace(".html", "").split("_")
            if len(parts) > 2:
                user_links.append(link)
            else:
                summary_links.append(link)
        elif fname.startswith("plan"):
            plan_links.append(link)
        else:
            summary_links.append(link)

    def _section(title: str, items: list[str]) -> str:
        if not items:
            return ""
        inner = "\n".join(items)
        return f"<h2>{_esc(title)}</h2>\n<ul>{inner}</ul>"

    body_parts = []
    if config.url:
        body_parts.append(f'<p><a href="{_esc(config.url)}">← Back to {config.name}</a></p>')
    body_parts.extend(
        [
            _section("Summaries (all users)", summary_links),
            _section("Per-user summaries", user_links),
            _section("Project plan", plan_links),
        ]
    )
    body = "\n".join(p for p in body_parts if p)

    generated_str = now.strftime("%Y-%m-%d %H:%M") if include_date else ""
    meta_line = f'<p class="meta">Generated: {generated_str}</p>' if generated_str else ""

    return _INDEX_HTML_TEMPLATE.format(
        title=_esc(config.name),
        meta=meta_line,
        body=body,
    )


_INDEX_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Reports</title>
<style>
  :root {{ --bg: #1e1e2e; --fg: #cdd6f4; --surface: #313244; --border: #45475a; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg);
          padding: 2rem; max-width: 900px; margin: 0 auto; line-height: 1.6; }}
  h1 {{ margin-bottom: .25rem; }}
  h2 {{ margin-top: 1.5rem; margin-bottom: .5rem; border-bottom: 1px solid var(--border); padding-bottom: .25rem; }}
  .meta {{ color: #a6adc8; font-size: .9rem; margin-bottom: 1rem; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ padding: .35rem 0; }}
  a {{ color: #89b4fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg: #eff1f5; --fg: #4c4f69; --surface: #e6e9ef; --border: #ccd0da; }}
    a {{ color: #1e66f5; }}
  }}
</style>
</head>
<body>
<h1>{title} — Reports</h1>
{meta}
{body}
</body>
</html>
"""


def cmd_report(fmt: str = "all", include_date: bool = False, offline: bool = False) -> None:
    """Generate a full set of project reports under the configured output directory.

    Creates:
    - summary_{period}.{ext} for day/week/month/year (all users)
    - summary_{period}_{user}.{ext} for week/month per user
    - plan.{ext} — project plan
    """
    project_root = get_project_root()
    if project_root is None:
        console.print("[red]No AIPM project found. Run 'aipm init' first.[/red]")
        return

    config = ProjectConfig.load(project_root)
    gen_dir = project_root / config.output_dir
    gen_dir.mkdir(parents=True, exist_ok=True)

    tickets = _collect_all_tickets(project_root)
    if not tickets:
        console.print("[yellow]No tickets found. Run 'aipm sync' first.[/yellow]")
        return

    write_md = fmt in ("md", "all")
    write_html = fmt in ("html", "all")

    assignees = _unique_assignees(tickets)
    files_written: list[str] = []
    html_index_entries: list[tuple[str, str]] = []  # (filename, label)

    with console.status("[bold]Generating reports...") as status:
        # 1. Summaries for all users by period
        for period in SUMMARY_PERIODS:
            status.update(f"  summary — {period} (all)...")
            md_text = _generate_summary_md(tickets, period, "all", config, include_date)
            name = f"summary_{period}"

            if write_md:
                path = gen_dir / f"{name}.md"
                path.write_text(md_text)
                files_written.append(str(path.relative_to(project_root)))
            if write_html:
                path = gen_dir / f"{name}.html"
                path.write_text(_md_to_html(md_text, f"{config.name} — {period.title()} Summary", config))
                files_written.append(str(path.relative_to(project_root)))
                html_index_entries.append((f"{name}.html", f"{period.title()} Summary (all users)"))

        # 2. Per-user summaries for week and month
        for user in assignees:
            for period in PER_USER_PERIODS:
                status.update(f"  summary — {period} ({user})...")
                md_text = _generate_summary_md(tickets, period, user, config, include_date)
                safe = user.lower().replace(" ", "_")
                name = f"summary_{period}_{safe}"

                if write_md:
                    path = gen_dir / f"{name}.md"
                    path.write_text(md_text)
                    files_written.append(str(path.relative_to(project_root)))
                if write_html:
                    path = gen_dir / f"{name}.html"
                    path.write_text(_md_to_html(md_text, f"{config.name} — {period.title()} Summary ({user})", config))
                    files_written.append(str(path.relative_to(project_root)))
                    html_index_entries.append((f"{name}.html", f"{period.title()} Summary ({user})"))

        # 3. Project plan
        status.update("  project plan...")
        if write_md:
            path = gen_dir / "plan.md"
            path.write_text(_generate_plan_md(tickets, config, include_date))
            files_written.append(str(path.relative_to(project_root)))
        if write_html:
            path = gen_dir / "plan.html"
            path.write_text(_generate_plan_html(tickets, config, include_date))
            files_written.append(str(path.relative_to(project_root)))
            html_index_entries.append(("plan.html", "Project Plan"))

        # 4. Index page
        if write_html:
            status.update("  index...")
            path = gen_dir / "index.html"
            path.write_text(_generate_index_html(config, html_index_entries, include_date))
            files_written.append(str(path.relative_to(project_root)))

    console.print(f"\n[green]Generated {len(files_written)} report(s) in {config.output_dir}/:[/green]")
    for f in files_written:
        console.print(f"  [dim]{f}[/dim]")
    console.print()
