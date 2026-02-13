# AIPM — The AI Project Manager

> Manage large projects distributed over multiple issue trackers and tools — from a single local workspace.

![](doc/images/aipm_summary_day.png)

AIPM syncs issues from **Jira** and **GitHub** into a local git-tracked directory of Markdown files. It then uses **GitHub Copilot** (with graceful fallback) to summarize changes, update project plans, and generate reports — all from the command line.

> **New here?** Start with the [Tutorial](doc/tutorial.md) — it walks you through setup, tickets, horizons, and daily workflow.\
> For the planning concept in depth, see [Planning & Time Horizons](doc/planning.md).\
> Learn how automated ticket checking works in [Check](doc/check.md).\
> Troubleshoot Copilot issues with [Debugging](doc/debug.md).

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


To uninstall:

```bash
just uninstall
```

### Copilot CLI (optional, recommended)

AIPM uses the [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/install-copilot-cli) for AI-powered analysis.
Without it, all features still work but fall back to keyword-based analysis.

The Python SDK (`github-copilot-sdk`) bundles its own Copilot CLI binary, so you don't need to install it separately.
However, you **must authenticate** it before first use:

```bash
# 1. Launch the bundled Copilot CLI in interactive mode:
.venv/lib64/python3.14/site-packages/copilot/bin/copilot

# 2. Inside the Copilot shell, type:
/login

# 3. Follow the OAuth device flow to authenticate with your GitHub account.
# 4. Once authenticated, exit the shell (Ctrl+D or /exit).
```

Alternatively, you can set a GitHub token in your environment:

```bash
export GITHUB_TOKEN="your-token-here"
```

**Manual Copilot CLI install** (useful for debugging and testing):

```bash
# Linux / macOS:
just install-copilot
# or manually:
curl -fsSL https://gh.io/copilot-install | bash

# Via npm (any platform):
npm install -g @github/copilot
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
  ticket   Manage local tickets.
```

</div>
</td></tr></table>
</div>

| Command | Description |
|---------|-------------|
| `aipm init` | Initialize a new project — creates `tickets/`, `generated/`, `milestones.md`, `goals.md`, `README.md`, and `aipm.toml` |
| `aipm add jira <URL>` | Add a Jira project as an issue source (with optional JQL filter) |
| `aipm add github <URL>` | Add a GitHub repository as an issue source |
| `aipm sync` | Fetch issues from all sources and write them as Markdown to `tickets/<source>/` |
| `aipm diff` | Summarize the currently staged git changes using AI (or structured fallback) |
| `aipm plan` | Update `milestones.md` based on current ticket horizons and statuses |
| `aipm summary [day\|week\|month\|year\|all] [all\|me\|username]` | Generate a project summary filtered by time horizon and user |
| `aipm ticket add` | Create a local ticket (interactive or via flags `-t`, `-p`, `-a`, `-d`, `-l`, `--horizon`, `--due`, `--repo`) |
| `aipm ticket list` | List all local tickets in a table |
| `aipm ticket upgrade` | Scan existing tickets and interactively fill in missing fields (horizon, priority, etc.) |
| `aipm check [TICKET_KEY]` | Check ticket completion against configured repos using Copilot |
| `aipm check --debug` | Check with full Copilot prompt/response output |
| `aipm commit` | Stage AIPM files, generate a commit message, and commit |

## Time Horizons

AIPM uses **time horizons** instead of rigid priority levels to organize work.
Every ticket carries a horizon that tells you _when_ it should be tackled:

| Horizon | Meaning |
|---------|---------|
| `now` | Drop everything — must be done today |
| `week` | Should be finished by end of this week |
| `next-week` | Needs to be done by end of next week |
| `month` | Sometime this or next month |
| `year` | Finish within the year; strategic |
| `sometime` | Nice-to-have; maybe later |

```bash
# Create a ticket with a horizon
aipm ticket add -t "Fix login crash" --horizon now -p high

# Link a ticket to a repo for checking
aipm ticket add -t "Add CI pipeline" --horizon week --repo /path/to/project

# Check if tasks are done (most urgent first)
aipm check

# Check a specific ticket
aipm check L-0001

# Urgent items only
aipm summary day

# This week's workload
aipm summary week

# Full picture
aipm summary all
```

Tickets can also carry an optional `--due YYYY-MM-DD` date. If a due date is set without
an explicit horizon, AIPM infers the horizon automatically.

See [doc/planning.md](doc/planning.md) for the full planning concept.

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
├── milestones.md      # Project milestones grouped by horizon
├── goals.md           # Project goals
├── generated/         # Generated reports (plan, kanban, etc.)
├── doc/               # Documentation
│   ├── check.md       # How automated ticket checking works
│   ├── debug.md       # Debugging and troubleshooting Copilot
│   ├── planning.md    # Planning concept and horizon reference
│   └── tutorial.md    # Getting started tutorial
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
