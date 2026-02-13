# Automated Ticket Checking

`aipm check` verifies whether your tickets have been completed by analyzing the git history of a linked repository. It works with or without GitHub Copilot — falling back to keyword matching and structured output when Copilot is unavailable.

## How It Works

The check runs in four steps for each ticket:

### 1. Read the git log

AIPM resolves the `Repo` field on the ticket (absolute path, relative path like `.`, or `~/…`) and reads the last 50 commits from that repository.

### 2. Filter commits by relevance

Only commits whose message relates to the ticket are kept. When Copilot is available it decides which commits match; otherwise AIPM extracts keywords from the ticket title and description and does a simple substring search on commit messages.

### 3. Fetch diffs for matching commits

For each relevant commit, `git show --stat --patch` is called to get the full diff. The diffs are truncated to ~12 000 characters so Copilot doesn't get overloaded.

### 4. Analyze with Copilot (or fallback)

The ticket description plus the relevant diffs are sent to Copilot, which returns:

- **Status** — `DONE`, `IN PROGRESS`, or `NOT STARTED`
- **Confidence** — High, Medium, or Low
- **Evidence** — which commits address the task
- **Remaining work** — what's still missing

When Copilot is unavailable the matching commits are listed so you can review them manually.

### 5. Interactive close

If the analysis concludes the ticket is **DONE**, AIPM asks whether you want to close it right there:

```
Close ticket L-0004? [Y/n]:
```

Accepting updates the ticket's status to `completed` and stages the file with git.

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
```

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