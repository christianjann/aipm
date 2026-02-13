# Automated Ticket Checking

`aipm check` verifies whether your tickets have been completed by analyzing the git history of a linked repository. It works with or without GitHub Copilot — falling back to keyword matching and structured output when Copilot is unavailable.

## How It Works

The check runs in three steps for each ticket:

### 1. Read the git log

AIPM resolves the `Repo` field on the ticket (absolute path, relative path like `.`, or `~/…`) and reads the last 50 commits from that repository.

### 2. Analyze commits with Copilot (or fallback)

All commit messages are sent to Copilot along with the ticket details. Copilot identifies which commits are relevant and returns:

- **Status** — `DONE`, `IN PROGRESS`, or `NOT STARTED`
- **Confidence** — High, Medium, or Low
- **Evidence** — which commits address the task
- **Remaining work** — what's still missing

When Copilot is unavailable, AIPM extracts keywords from the ticket title and description and matches them against commit messages. The matching commits are listed so you can review them manually.

### 3. Interactive close

If the analysis concludes the ticket is **DONE**, AIPM asks whether you want to close it:

```
Close ticket L-0004? [Y/n/c] (c=commit):
```

- **y** — mark as completed and stage the ticket file
- **n** — skip (default when not done)
- **c** — mark as completed, stage, and commit with message `AIPM: Marked L-0004 as completed`

## Copilot-unavailable fallback

![](images/aipm_check_copilot_unavailable.png)

Without Copilot the output is still useful — you see the matched commits and can decide yourself whether the task is done.

## Usage

```bash
# Check all open tickets (most urgent first)
aipm check

# Check a single ticket
aipm check L-0001

# Limit to the 3 most urgent
aipm check -n 3

# Debug mode — show full Copilot prompt and response
aipm check --debug
```

See [Debugging AIPM](debug.md) for troubleshooting Copilot responses.

## Configuring the repo

Add a repo when creating a ticket:

```bash
aipm ticket add -t "Add CI pipeline" --horizon week --repo /path/to/project
```

Or use `.` to point at the current project:

```bash
aipm ticket add -t "Write tests" --repo .
```

Existing tickets can be updated interactively:

```bash
aipm ticket upgrade
```

Relative paths are resolved against the AIPM project root, so `repo: .` always means "this project".