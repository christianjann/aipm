# MarkDown ticket format with Frontmatter

We are using a [Jekyll-style YAML front matter](https://jekyllrb.com/docs/front-matter/) for ticket attributes, similar to [agent skills](https://agentskills.io/specification).

## Directory Structure

Each ticket is stored in its own directory under `tickets/local/` (for local tickets) or `tickets/{source_name}/` for synced tickets, where `{source_name}` is the name assigned when adding the issue source.

You can add multiple sources of the same type (e.g., multiple Jira projects or GitHub repositories), each with its own name and subdirectory under `tickets/`.

```
tickets/
├── local/                    # Local tickets
│   ├── 000001_fix_login_bug/
│   │   └── ISSUE.md
│   └── 000002_add_feature/
│       └── ISSUE.md
├── MYPROJ/                   # Jira source named "MYPROJ"
│   ├── MYPROJ-123_fix_bug/
│   │   └── ISSUE.md
│   └── MYPROJ-456_add_docs/
│       └── ISSUE.md
└── myrepo/                   # GitHub source named "myrepo"
    ├── 42_implement_api/
    │   └── ISSUE.md
    └── 87_update_readme/
        └── ISSUE.md
```

Each ticket directory contains:
```
├── assets/           # Attachments, images, documents
├── scripts/          # Executable scripts related to the ticket
└── references/       # Additional documentation
```

The directory name follows the pattern `{number}_{sanitized_title}`, where:
- `number` is a 6-digit zero-padded sequential number (e.g., `000001`)
- `sanitized_title` is the title converted to lowercase, replacing spaces and special characters with underscores, limited to 60 characters

## ISSUE.md Format

## Front Matter Fields

The YAML front matter contains all ticket metadata. Required fields are marked with `*`.

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| **key** | string | * | Unique ticket identifier | "L-000001" |
| **title** | string | * | Ticket title | "Fix login bug" |
| **status** | string | * | Current status | "open", "in-progress", "completed" |
| **priority** | string | * | Priority level | "critical", "high", "medium", "low" |
| **horizon** | string | * | Time horizon | "now", "week", "month", "year", "sometime" |
| **source** | string | * | Source system | "local", "jira", "github" |
| **assignee** | string |  | Assigned user | "john.doe" |
| **due** | string |  | Due date (YYYY-MM-DD) | "2025-12-31" |
| **repo** | string |  | Git repository URL or path | "https://github.com/org/repo" or "." |
| **summary** | string |  | Short summary of the ticket (used when querying for description/summary) |
| **labels** | list |  | Tags/labels | ["bug", "frontend", "urgent"] |
| **url** | string |  | External URL (for synced tickets) | "https://github.com/org/repo/issues/123" |

## Complete Example

```yaml
---
key: "L-000001"
title: "Fix critical login bug in user authentication"
status: "open"
priority: "critical"
horizon: "now"
source: "local"
assignee: "alice"
due: "2025-02-20"
repo: "."
summary: "Users cannot log in due to authentication service failure"
labels: ["bug", "security", "frontend"]
---

## Description

Description text goes here. This can include:

- Steps to reproduce the issue
- Expected vs actual behavior
- Implementation notes
- Links to related issues
```

If no `summary` field is provided in the front matter, the entire description section will be used when querying for ticket summaries.

## File References

When referencing files in ticket directories, use relative paths from the ticket root:

```
See [the design document](references/design.md) for details.

Check the [test script](scripts/test_login.py) for reproduction steps.

View the [error screenshot](assets/error.png).
```

Keep file references one level deep from `ISSUE.md`. Avoid deeply nested reference chains.

## Viewing Tickets in VS Code

For the best experience viewing tickets with YAML front matter in VS Code, install the [Markdown Preview Enhanced](https://github.com/shd101wyy/vscode-markdown-preview-enhanced) extension.

To enable front matter rendering as a table:

1. Open VS Code settings (Ctrl/Cmd + ,)
2. Search for "markdown-preview-enhanced"
3. Find the "Front Matter Rendering Option" setting
4. Set it to "table"

This will display the YAML front matter as a nicely formatted table at the top of the preview.

## Migration from Table Format

The old format used a Markdown table for metadata:

```markdown
# L-000001: Fix critical login bug

| Field | Value |
|-------|-------|
| **Status** | open |
| **Priority** | critical |
| **Horizon** | now |
| **Assignee** | alice |
| **Due** | 2025-02-20 |
| **Repo** | . |
| **Source** | local |

## Description

Description here...
```

This will be migrated to the front matter format shown above.
