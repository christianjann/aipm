# AIPM — The AI Project Manager

> Manage large projects distributed over multiple issue trackers and tools — from a single local workspace.

AIPM syncs issues from **Jira** and **GitHub** into a local git-tracked directory of Markdown files. It then uses **GitHub Copilot** (with graceful fallback) to summarize changes, update project plans, and generate reports — all from the command line.

---

## Features

- **Multi-source sync** — pull issues from Jira and GitHub into one unified `tickets/` directory
- **Markdown-first** — every ticket, milestone, and goal is a plain Markdown file, version-controlled with git
- **AI-powered insights** — diff summaries, plan updates, and project reports powered by the GitHub Copilot SDK
- **Works offline** — all AI features fall back to structured local analysis when Copilot is unavailable
- **Simple CLI** — seven commands cover the full project management lifecycle

## Installation

Requires **Python 3.14+** and [uv](https://docs.astral.sh/uv/).

### Local (development)

```bash
uv sync
uv run aipm <command>
```

### Global (available everywhere)

Install `aipm` so it's available in any terminal session:

```bash
just install
# or manually:
uv tool install -e .
```

If `~/.local/bin` is not on your `PATH`, add it:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then use `aipm` directly:

```bash
aipm <command>
```

<div align="center">
<table><tr><td>
<div style="background:#1e1e1e;border-radius:8px;overflow:hidden;border:1px solid #444;">

<!-- Title bar -->
<div style="background:#333;padding:6px 12px;display:flex;align-items:center;">
🔴 🟡 🟢 &nbsp;&nbsp;<code style="color:#aaa;background:transparent;">~/my-project</code>
</div>

```
❯ aipm --help
Usage: aipm [OPTIONS] COMMAND [ARGS]...

  AIPM - The AI Project Manager.

  Manage large projects distributed over multiple issue trackers and tools.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  add      Add an issue source to the project.
  commit   Commit the updated tickets and plan.
  diff     Summarize changes currently staged for commit.
  init     Initialize a new AIPM project in the current directory.
  plan     Update the project plan based on current ticket status.
  summary  Generate a high-level project summary.
  sync     Sync issues from all configured sources to the tickets directory.
```

</div>
</td></tr></table>
</div>

To uninstall:

```bash
just uninstall
```

## Quick Start

```bash
# 1. Initialize a new project
uv run aipm init

# 2. Connect your issue trackers
uv run aipm add jira https://mycompany.atlassian.net/browse/PROJ
uv run aipm add github https://github.com/owner/repo

# 3. Sync issues to local Markdown files
uv run aipm sync

# 4. Review what changed
uv run aipm diff

# 5. Update the project plan
uv run aipm plan

# 6. Get a summary
uv run aipm summary week

# 7. Commit everything
uv run aipm commit
```

## Commands

| Command | Description |
|---------|-------------|
| `aipm init` | Initialize a new project — creates `tickets/`, `generated/`, `milestones.md`, `goals.md`, `README.md`, and `aipm.toml` |
| `aipm add jira <URL>` | Add a Jira project as an issue source (with optional JQL filter) |
| `aipm add github <URL>` | Add a GitHub repository as an issue source |
| `aipm sync` | Fetch issues from all sources and write them as Markdown to `tickets/<source>/` |
| `aipm diff` | Summarize the currently staged git changes using AI (or structured fallback) |
| `aipm plan` | Update `milestones.md` based on current ticket statuses |
| `aipm summary [day\|week\|month\|year] [all\|me\|username]` | Generate a high-level project summary for a given period and user |
| `aipm ticket add` | Create a local ticket (interactive or via flags `-t`, `-p`, `-a`, `-d`, `-l`) |
| `aipm ticket list` | List all local tickets in a table |
| `aipm commit` | Stage AIPM files, generate a commit message, and commit |

## Project Structure

After running `aipm init`, your workspace will look like this:

```
my-project/
├── aipm.toml          # Project configuration and source definitions
├── tickets/           # Synced issue tickets (one .md per issue)
│   ├── local/         # Local-only tickets
│   │   ├── 0001_setup_ci.md
│   │   └── 0002_write_docs.md
│   ├── PROJ/          # Jira source
│   │   ├── PROJ-1_implement_feature.md
│   │   └── PROJ-2_fix_bug.md
│   └── repo/          # GitHub source
│       ├── 42_add_readme.md
│       └── 87_refactor_api.md
├── milestones.md      # Project milestones and timeline
├── goals.md           # Project goals
├── generated/         # Generated reports (plan, kanban, etc.)
└── README.md          # Project summary
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_TOKEN` | For Jira sources | Jira API token or personal access token |
| `JIRA_EMAIL` | For Jira Cloud | Email address for Jira Cloud basic auth |
| `GITHUB_TOKEN` | For private repos | GitHub personal access token |

## Development

```bash
# Install with dev dependencies
uv sync

# Run linter
uv run ruff check src/

# Run type checker
uv run ty check src/

# Run tests
uv run pytest tests/ -v
```

## License

MIT
