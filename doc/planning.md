# AIPM Planning — Time Horizons

## Philosophy

Traditional priority systems (critical / high / medium / low) answer _"how important is this?"_
but not _"when should I work on this?"_. AIPM replaces rigid priority with **time horizons** —
a lightweight system that tells you exactly what belongs on your plate right now and what can wait.

Every ticket carries a **horizon** that describes when it should be tackled:

| Horizon       | Meaning                                                      |
|---------------|--------------------------------------------------------------|
| `now`         | Drop everything — this must be done today.                   |
| `week`        | Should be finished by the end of this week.                  |
| `next-week`   | Needs to be done by the end of next week.                    |
| `month`       | Sometime this or next month — no rush yet.                   |
| `year`        | Finish within the year; strategic but not urgent.            |
| `sometime`    | Nice-to-have; maybe next year, maybe later.                  |

Horizons are intentionally fuzzy — they are _commitments_, not deadlines-to-the-minute.
The idea is borrowed from time-blocking methodologies: by sorting work into temporal
buckets you always know what to focus on without drowning in a flat, undifferentiated backlog.

## How Horizons Interact with Status

Status and horizon are orthogonal:

- **Status** tracks _progress_: open → in progress → done.
- **Horizon** tracks _urgency_: when should work on this begin or finish?

A ticket that is `now` + `open` means you should start immediately.
A ticket that is `sometime` + `in progress` means someone picked it up early — fine.

When you run `aipm summary` or `aipm plan`, tickets are first filtered by horizon
relevance to the requested period, then grouped by status within each horizon section.

## Setting Horizons

### On Local Tickets

```bash
# Interactive — you'll be prompted for a horizon
aipm ticket add

# Explicitly via flags
aipm ticket add -t "Fix login crash" --horizon now
aipm ticket add -t "Write API docs" --horizon month
```

### On Synced Tickets

Tickets synced from Jira or GitHub get their horizon from:

1. A **labels / custom-field mapping** (e.g., a Jira label `horizon:week`).
2. The **due date** — AIPM auto-calculates the nearest horizon.
3. Fallback: `sometime` (unplanned work stays in the long-term bucket).

You can always override the horizon locally by editing the ticket markdown file.

### Due Dates

Tickets can optionally carry a `due` date (YYYY-MM-DD). If a due date is set but
no explicit horizon is provided, AIPM will infer the horizon automatically:

| Due date falls within | Inferred horizon |
|-----------------------|------------------|
| Today                 | `now`            |
| This week             | `week`           |
| Next week             | `next-week`      |
| This or next month    | `month`          |
| This year             | `year`           |
| Beyond this year      | `sometime`       |

## Planning Commands

### `aipm plan`

Generates an updated `milestones.md` grouped by horizon:

```
# My Project - Milestones

## Now (2 tickets)
- [ ] Fix login crash (Alice)
- [ ] Hotfix payment gateway

## This Week (3 tickets)
- [ ] Add rate limiting
- [ ] Update API docs
- [ ] Review PR #42

## Next Week (1 ticket)
- [ ] Migrate database schema

## This Month (4 tickets)
- [ ] Refactor auth module
- [ ] Add monitoring dashboard
...

## Sometime (5 tickets)
- [ ] Rewrite legacy module
...
```

### `aipm summary [period]`

Generates a summary scoped to a time window. The `period` argument controls
which horizons are included:

| Period    | Horizons included                               |
|-----------|--------------------------------------------------|
| `day`     | `now`                                            |
| `week`    | `now` + `week`                                   |
| `month`   | `now` + `week` + `next-week` + `month`           |
| `year`    | all except `sometime`                            |
| `all`     | everything                                       |

This means `aipm summary day` shows only the urgent fires, while
`aipm summary month` gives a broader planning view.

## Workflow Example

```bash
# Morning stand-up — what's hot?
aipm summary day

# Weekly planning — what should be done this week?
aipm summary week

# Sprint planning — broader view
aipm summary month

# Quarterly review — strategic outlook
aipm summary year

# Update the plan file
aipm plan
```

## Changing a Ticket's Horizon

Edit the ticket's markdown file directly — change the `Horizon` field in the table:

```markdown
| **Horizon** | week |
```

Or re-create the ticket with a different horizon flag. Horizons are just data —
there's no workflow enforcement. Move things around as priorities shift.

## Design Rationale

- **Why not just priority?** Priority creates a false hierarchy. Everything marked
  "critical" competes for attention equally. Horizons add the missing dimension of _time_.
- **Why not strict deadlines?** Deadlines are useful (that's why `due` exists) but
  most work sits in fuzzy time buckets. Horizons match how people actually think about
  their workload: "this week", "sometime", etc.
- **Why keep priority too?** Priority still matters for ordering within a horizon.
  Two `now` tickets with different priorities? Do the higher-priority one first.
  Priority is retained as a secondary sort axis.
