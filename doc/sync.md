# Ticket sync

AIPM can sync issues from external sources like Jira and GitHub, bringing them into your local workspace as Markdown files. This allows you to work with issues from multiple trackers in one unified view.

## Adding issue sources

Before you can sync issues, you need to add one or more issue sources to your project. Each source gets its own subdirectory under `tickets/` where its issues will be stored.

### Adding a Jira source

```bash
aipm add jira https://yourcompany.atlassian.net/browse/PROJ
```

This will:
1. Parse the URL to extract the Jira server URL and project key
2. Prompt you for:
   - **Project key** (defaults to the key from URL, e.g., "PROJ")
   - **JQL filter** (optional, defaults to `project = PROJ ORDER BY updated DESC`)
   - **Source name** (friendly name for this source, defaults to project key)

Example interaction:
```
Jira project key (e.g., PROJ) [PROJ]: MYPROJ
Want to set a custom JQL filter? [y/N]: y
JQL filter [project = MYPROJ ORDER BY updated DESC]: project = MYPROJ AND status != Closed
Source name [MYPROJ]: My Project
```

This creates a source named "My Project" that will sync to `tickets/My Project/`.

### Adding a GitHub source

```bash
aipm add github https://github.com/owner/repo
```

This will:
1. Parse the repository information from the URL
2. Prompt you for:
   - **Issue state filter** (open/closed/all, defaults to "open")
   - **Source name** (friendly name, defaults to repository name)

Example interaction:
```
Issue state filter [open]: all
Source name [repo]: my-repo
```

This creates a source named "my-repo" that will sync to `tickets/my-repo/`.

### Managing sources

Sources are stored in your `aipm.toml` configuration file. You can add multiple sources of the same type:

```bash
# Add multiple Jira projects
aipm add jira https://company.atlassian.net/browse/PROJ1
aipm add jira https://company.atlassian.net/browse/PROJ2

# Add multiple GitHub repos
aipm add github https://github.com/org/repo1
aipm add github https://github.com/org/repo2
```

Each source gets its own subdirectory under `tickets/`.

## Syncing with remote projects

Once you've added sources, you can sync issues from all configured sources:

```bash
aipm sync
```

This will:
1. Connect to each configured source
2. Fetch all issues matching the configured filters
3. Create/update ticket folders under `tickets/{source_name}/`
4. Each issue becomes a folder with an `ISSUE.md` file

### Sync behavior

- **Incremental**: Only fetches issues that have been updated since the last sync
- **Safe**: Never deletes local tickets, only adds/updates
- **Structured**: Issues are organized in folders with frontmatter metadata

### Example synced structure

```
tickets/
├── local/           # Local tickets
│   ├── 000001_fix_bug/
│   │   └── ISSUE.md
│   └── 000002_add_feature/
│       └── ISSUE.md
├── My Project/      # Jira source "My Project"
│   ├── MYPROJ-123_critical_bug/
│   │   └── ISSUE.md
│   └── MYPROJ-456_feature_request/
│       └── ISSUE.md
└── my-repo/         # GitHub source "my-repo"
    ├── 42_implement_api/
    │   └── ISSUE.md
    └── 87_update_docs/
        └── ISSUE.md
```

### Environment variables

You'll need to set authentication tokens for private repositories:

```bash
# For Jira
export JIRA_TOKEN="your-jira-api-token"
export JIRA_EMAIL="your-email@company.com"  # Required for Jira Cloud

# For private GitHub repos
export GITHUB_TOKEN="your-github-token"
```

### Troubleshooting sync

If sync fails:
1. Check your authentication tokens are set correctly
2. Verify the source URLs and credentials are valid
3. Use `aipm sync --verbose` for more detailed output
4. Check network connectivity to the issue tracker

### Removing sources

To remove a source, edit `aipm.toml` and remove the corresponding entry from the `sources` array. The ticket files will remain in `tickets/` but won't be updated on future syncs.
