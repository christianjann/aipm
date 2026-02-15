---
name: aipm-create-ticket
description: Create a new ticket using AIPM — The AI Project Manager
---

This skill creates a new local ticket in an AIPM project. The ticket will be saved as a Markdown file in the `tickets/local/` directory with an auto-generated sequential number (e.g., `000001_fix_bug/ISSUE.md`).

## Usage

```bash
aipm ticket add -t "Fix login bug" -p high -h now --due 2026-02-20
```

## Interactive Mode

If you run `aipm ticket add` without any arguments, it will prompt you interactively for all required information.

## Examples

### Simple ticket
```bash
aipm ticket add -t "Update documentation"
```

### Full-featured ticket
```bash
aipm ticket add \
  -t "Implement user authentication" \
  -d "Add OAuth2 login flow with Google and GitHub providers" \
  -p high \
  -h week \
  -a "alice" \
  --due 2026-03-01 \
  --repo https://github.com/myorg/myproject \
  -l "backend,security"
```

## Parameters

- **title** (required): The ticket title
- **description** (optional): Detailed description of the ticket
- **priority** (optional, default: "medium"): Priority level (critical, high, medium, low)
- **horizon** (optional, default: "sometime"): Time horizon (now, week, next-week, month, year, sometime)
- **assignee** (optional): Person assigned to the ticket
- **due** (optional): Due date in YYYY-MM-DD format
- **repo** (optional): Git repository URL or local path for completion checking
- **labels** (optional): Comma-separated list of labels

## Output

The command outputs:
- Confirmation of ticket creation with key and title
- Horizon and due date (if set)
- File path where the ticket was saved
- The ticket file is automatically staged in git

## Notes

- Tickets are stored in `tickets/local/` with sequential numbering
- The ticket key format is `L-XXXX` where XXXX is the sequential number
- Tickets can be linked to repositories for automated completion checking via `aipm check`
