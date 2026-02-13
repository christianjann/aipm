# AIPM Tutorial — Getting Started

This tutorial walks you through AIPM from zero to a fully managed project.
By the end you'll know how to create tickets, organize them with time horizons,
connect external issue trackers, and use summaries and plans to stay on top of your work.

---

## Prerequisites

- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)** — the fast Python package manager
- **git** — AIPM is designed around git-tracked workspaces

Install AIPM globally so it's available everywhere:

```bash
uv tool install -e /path/to/aipm
```

Or run it locally during development:

```bash
uv sync
uv run aipm --version
```

---

## Step 1: Initialize Your First Project

Navigate to your project directory (or create a new one) and run:

```bash
mkdir my-project && cd my-project
git init
aipm init
```

You'll be asked for a project name and description:

```
❯ aipm init
Project name [my-project]: My Web App
Project description: Backend and frontend for the web app
  Created tickets/
  Created tickets/local/
  Created generated/
  Created milestones.md
  Created goals.md
  Created README.md
  Created aipm.toml

Project 'My Web App' initialized!
```

Take a look at what was created:

```
my-project/
├── aipm.toml       ← project config
├── tickets/
│   └── local/      ← your local tickets go here
├── milestones.md   ← auto-updated by `aipm plan`
├── goals.md        ← define what success looks like
├── generated/      ← AI-generated reports land here
└── README.md       ← project overview
```

**Tip:** Open `goals.md` and write down 2–3 goals for your project.
AIPM reads this file when generating plans and summaries.

---

## Step 2: Create Your First Tickets

### Interactive mode

Just run `aipm ticket add` with no flags — AIPM will walk you through it:

```
❯ aipm ticket add
Ticket title: Set up CI pipeline
Description (optional): GitHub Actions for lint, test, build
Priority: medium
Horizon: week
Due date (YYYY-MM-DD, optional):
Assignee (optional):

Created ticket: L-0001 — Set up CI pipeline
  Horizon: week
  File: tickets/local/0001_set_up_ci_pipeline.md
```

### One-liner mode

If you already know what you want, skip the prompts:

```bash
aipm ticket add -t "Fix login crash" --horizon now -p critical
aipm ticket add -t "Write API docs" --horizon month -p low
aipm ticket add -t "Refactor auth module" --horizon sometime
```

### Understanding horizons

Every ticket has a **time horizon** — it answers _"when should I do this?"_:

| Horizon       | When to use it                               |
|---------------|----------------------------------------------|
| `now`         | On fire. Do it today.                        |
| `week`        | Finish by end of this week.                  |
| `next-week`   | Can wait, but not longer than next week.     |
| `month`       | This or next month. No rush.                 |
| `year`        | Strategic work — sometime this year.         |
| `sometime`    | Backlog. Maybe next year, maybe never.       |

If you're unsure, pick `sometime` — you can always change it later.

---

## Step 3: View Your Tickets

List everything you've created:

```bash
aipm ticket list
```

```
              Local Tickets
┌────────┬──────────────────────┬────────┬─────────┬─────┬──────────┬──────────┐
│ Key    │ Title                │ Status │ Horizon │ Due │ Priority │ Assignee │
├────────┼──────────────────────┼────────┼─────────┼─────┼──────────┼──────────┤
│ L-0001 │ Set up CI pipeline   │ open   │ week    │     │ medium   │          │
│ L-0002 │ Fix login crash      │ open   │ now     │     │ critical │          │
│ L-0003 │ Write API docs       │ open   │ month   │     │ low      │          │
│ L-0004 │ Refactor auth module │ open   │ sometime│     │ medium   │          │
└────────┴──────────────────────┴────────┴─────────┴─────┴──────────┴──────────┘
```

Each ticket is a plain Markdown file — open any of them in your editor and
change fields directly if you like. There's no database, no lock-in.

---

## Step 4: Get a Summary

Summaries filter your tickets by time horizon, so you only see what's relevant:

```bash
# What needs my attention RIGHT NOW?
aipm summary day

# What's on my plate this week?
aipm summary week

# Broader planning view
aipm summary month

# Everything, including the backlog
aipm summary all
```

**How filtering works:**

| Command            | Shows horizons                       |
|--------------------|--------------------------------------|
| `aipm summary day` | `now`                                |
| `aipm summary week`| `now` + `week`                       |
| `aipm summary month`| `now` + `week` + `next-week` + `month` |
| `aipm summary year`| everything except `sometime`         |
| `aipm summary all` | everything                           |

Start your day with `aipm summary day` to see what's urgent.
Use `aipm summary week` during your weekly planning.

---

## Step 5: Update the Plan

```bash
aipm plan
```

This reads all your tickets, groups them by horizon, and writes an updated
`milestones.md`. Open the file to see a structured overview:

```markdown
# My Web App — Milestones

## Now — urgent (1)
- [ ] Fix login crash

## This Week (1)
- [ ] Set up CI pipeline

## This / Next Month (1)
- [ ] Write API docs

## Sometime (1)
- [ ] Refactor auth module
```

Run `aipm plan` whenever you want a fresh snapshot of where things stand.

---

## Step 6: Connect External Issue Trackers (Optional)

AIPM really shines when you pull in tickets from Jira, GitHub, or both.

### Add a GitHub repository

```bash
aipm add github https://github.com/myorg/my-repo
```

### Add a Jira project

```bash
aipm add jira https://mycompany.atlassian.net/browse/PROJ
```

Set the required environment variables first:

```bash
# For GitHub (needed for private repos)
export GITHUB_TOKEN="ghp_..."

# For Jira
export JIRA_TOKEN="your-api-token"
export JIRA_EMAIL="you@company.com"
```

### Sync issues

```bash
aipm sync
```

This fetches all issues from your connected sources and writes them as
Markdown files under `tickets/<source>/`. Each file looks like a local ticket
but includes the original URL and source metadata.

---

## Step 7: Review Changes and Commit

After syncing, creating tickets, or updating the plan, review what changed:

```bash
aipm diff
```

This summarizes the staged git changes — what tickets were added, updated,
or resolved. If GitHub Copilot is available it generates a natural-language
summary; otherwise you get a structured breakdown.

When you're happy, commit everything in one go:

```bash
aipm commit
```

AIPM stages all project files (`tickets/`, `milestones.md`, `goals.md`, etc.),
generates a commit message, asks you to confirm, and commits.

---

## Step 8: Upgrade Old Tickets

If you created tickets before the horizon feature existed (or forgot to set one),
bulk-upgrade them:

```bash
aipm ticket upgrade
```

AIPM scans all local tickets, finds ones missing required fields (horizon, priority),
and walks you through each one:

```
❯ aipm ticket upgrade
Scanning 4 local ticket(s) for missing fields...

L-0003: Write API docs
  Missing: horizon
  Update this ticket? [Y/n]: y
  Horizon: month
  Updated!

Done: 1 upgraded, 0 skipped, 3 already complete.
```

---

## Daily Workflow Cheat Sheet

Here's what a typical day looks like with AIPM:

```bash
# Morning: what's urgent?
aipm summary day

# Check the week
aipm summary week

# Thought of something? Create a ticket
aipm ticket add -t "Add rate limiting" --horizon week -p high

# Finished a task? Edit the ticket file — change Status to "done"
# Or just delete the file if you don't need it

# End of day: update the plan and commit
aipm plan
aipm commit
```

### Weekly planning session

```bash
# Pull latest from issue trackers
aipm sync

# See the full picture
aipm summary month

# Review and adjust horizons in your ticket files
# Move "sometime" items to "week" if they're now urgent

# Update milestones and commit
aipm plan
aipm commit
```

---

## Tips and Tricks

### Edit tickets directly

Every ticket is a Markdown file. Change the horizon, status, priority, or
description by editing the file in your editor. No special commands needed.

```markdown
| **Horizon** | now |        ← change "week" to "now"
| **Status** | in progress |  ← started working on it
```

### Use due dates

Add a due date and AIPM will auto-infer the horizon:

```bash
aipm ticket add -t "Submit report" --due 2026-02-15
# → horizon is auto-set based on how far away the date is
```

### Filter summaries by user

```bash
aipm summary week alice    # only Alice's tickets
aipm summary month me      # only yours
```

### Quick one-liners

```bash
aipm ticket add -t "hotfix: payment gateway" --horizon now -p critical
aipm summary day
aipm plan && aipm commit
```

---

## What's Next?

- Read the [Planning Concept](planning.md) to understand horizons in depth
- Define your project goals in `goals.md`
- Connect your first external issue tracker with `aipm add`
- Run `aipm --help` on any command for detailed usage

Happy planning!
