# 5. Core User Experience — Single-Page Worklog

Worklog is intentionally a **single-page web application**.

There is no traditional application navigation, sidebar, project dashboard, analytics section, or separate GitHub page.

The entire product revolves around one continuous chronological worklog.

The page should answer one question:

> **What have I been working on?**

The interface consists of three primary areas:

```text
┌──────────────────────────────────────────────────────────────┐
│ WORKLOG                                      GitHub ●        │
│ Building, learning, debugging, shipping.                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [ Write today's worklog... ]                                │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  SEPTEMBER 2026                                              │
│                                                              │
│  Sep 10 · 6h                                  NOT SHIPPED    │
│  FastAPI Setup                                               │
│                                                              │
│  Continued to work on my module for complete setup...        │
│                                                              │
│  Blocker                                                     │
│  Configuration · Server Security · Logging                   │
│                                                              │
│  Next → Server Deployment · Backend Development              │
│                                                              │
│  ▸ Detailed Notes                                            │
│  ▸ GitHub activity · 8 commits                               │
│                                                              │
│  ─────────────────────────────────────────────────────────   │
│                                                              │
│  Sep 09 · 4h                                      SHIPPED    │
│  Backend Development                                        │
│  ...                                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The three main UI components are therefore:

**Header**

Very small product identity and optional GitHub connection/status.

**Worklog Composer**

Used to create today's worklog.

**Worklog Feed**

A continuous reverse-chronological history of work.

There should be no navbar unless future requirements make one necessary.

---

# 6. Worklog Composer

The composer should mirror the structure of the underlying Markdown worklog while avoiding the feeling of filling out a large form.

Creating a worklog should still feel lightweight.

The initial state can simply show:

```text
+ Add today's worklog...
```

Selecting it expands the composer.

Example:

```text
┌────────────────────────────────────────────────────────────┐
│ Sep 17, 2026                                               │
│                                                            │
│ What did you work on?                                      │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Implemented authentication handlers...                 │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ Track                                                      │
│ [ FastAPI Setup ]                                          │
│                                                            │
│ Hours        Shipped                                       │
│ [ 6 ]        [ ○ ]                                         │
│                                                            │
│ Blockers                                                   │
│ [ Configuration, Server Security, Logging ]                │
│                                                            │
│ Next                                                       │
│ [ Server Deployment ] [ Backend Development ]              │
│                                                            │
│ Detailed Notes                                             │
│ [ Markdown supported...                                  ] │
│                                                            │
│ Quick Summary                                              │
│ [ What did you learn / struggle with?                    ] │
│                                                            │
│ [ Add image ]                              Save Worklog     │
└────────────────────────────────────────────────────────────┘
```

The composer converts these fields into the Worklog Markdown format automatically.

Users should not be required to manually construct YAML frontmatter.

---

# 7. Worklog Data Structure

The primary Worklog data model should closely follow the user's existing `.md` format.

A Worklog entry represents **one work session/day**, rather than an individual social-media-style post.

The canonical Markdown format is:

```markdown
---
date: 2026-09-10
tracks: [FastAPI Setup]
hours: 6
shipped: false
blocker: Configuration, Server Security and Logging
next: [Server Deployment, Backend Development]
---

# 📝 Worklog: 2026-09-10

## ⏱️ Activity Breakdown

Continued to work on my module for complete setup of REST APIs and making functional handlers with FastAPI in Python

## 🛠️ Detailed Notes

## 💡 Quick Summary

I've had a lot of mental blocks that tests my critical thinking and in-depth Python knowledge in implementing proper logic to my code.

* Total time invested: **6 hours**.
```

---

## 7.1 Core Worklog Schema

The database representation should closely correspond to this structure:

```text
Worklog
├── id
├── date
├── tracks[]
├── hours
├── shipped
├── blockers[]
├── next[]
├── activity_breakdown
├── detailed_notes
├── quick_summary
├── images[]
├── github_activity[]
├── created_at
└── updated_at
```

### Example

```json
{
  "date": "2026-09-10",
  "tracks": [
    "FastAPI Setup"
  ],
  "hours": 6,
  "shipped": false,
  "blockers": [
    "Configuration",
    "Server Security",
    "Logging"
  ],
  "next": [
    "Server Deployment",
    "Backend Development"
  ],
  "activity_breakdown": "Continued to work on my module for complete setup of REST APIs and making functional handlers with FastAPI in Python.",
  "detailed_notes": "",
  "quick_summary": "I've had a lot of mental blocks that tested my critical thinking and in-depth Python knowledge in implementing proper logic to my code.",
  "images": [],
  "github_activity": []
}
```

---

# 7.2 Field Definitions

### Date

```yaml
date: 2026-09-10
```

Required.

Represents the date the work occurred.

This should default to today's date when creating a new entry.

---

### Tracks

```yaml
tracks: [FastAPI Setup]
```

Represents the main development topics or areas worked on.

Multiple tracks should be supported:

```yaml
tracks: [FastAPI Setup, Authentication, PostgreSQL]
```

Tracks should behave like lightweight labels rather than requiring a separate project-management system.

UI:

```text
FastAPI Setup   Authentication   PostgreSQL
```

---

### Hours

```yaml
hours: 6
```

Represents total time invested for the worklog.

Allow decimal values:

```yaml
hours: 2.5
```

The application should not require timers.

The user simply records the final amount.

---

### Shipped

```yaml
shipped: false
```

Boolean representing whether meaningful work was shipped/completed during the session.

Display compactly:

```text
● SHIPPED
```

or:

```text
○ IN PROGRESS
```

Avoid giving this field excessive visual prominence.

---

### Blockers

Existing Markdown:

```yaml
blocker: Configuration, Server Security and Logging
```

Internally, Worklog should preferably normalize this into multiple blockers:

```text
Configuration
Server Security
Logging
```

This makes the information easier to display and eventually analyze.

The Markdown format can optionally evolve toward:

```yaml
blockers: [Configuration, Server Security, Logging]
```

However, the parser should support the existing singular `blocker:` syntax for compatibility.

---

### Next

```yaml
next: [Server Deployment, Backend Development]
```

Represents intended next steps.

Display as:

```text
Next → Server Deployment · Backend Development
```

These are informational rather than task-management objects.

There are no:

- deadlines;
- assignments;
- Kanban boards;
- priorities;
- task statuses.

Worklog should not accidentally become another project-management application.

---

# 7.3 Activity Breakdown

Corresponds to:

```markdown
## ⏱️ Activity Breakdown
```

This should describe **what was actually done during the work session.**

Example:

> Continued to work on my module for complete setup of REST APIs and making functional handlers with FastAPI in Python.

This should normally be the most visible textual part of an entry.

In the collapsed timeline:

```text
Sep 10 · 6h · FastAPI Setup

Continued to work on my module for complete setup of REST
APIs and making functional handlers with FastAPI in Python.

Blockers: Configuration · Server Security · Logging
Next → Server Deployment · Backend Development
```

---

# 7.4 Detailed Notes

Corresponds to:

```markdown
## 🛠️ Detailed Notes
```

This is the long-form technical journal.

It can contain:

- implementation notes;
- code snippets;
- commands;
- configuration changes;
- debugging observations;
- architectural decisions;
- links;
- screenshots;
- errors encountered;
- solutions discovered.

Full Markdown should be supported.

For example:

```markdown
## 🛠️ Detailed Notes

The main issue was caused by the middleware order.

```python
app.add_middleware(...)
```

Moving the authentication middleware before the logging
middleware resolved the issue.

![Middleware test](./images/test.png)
```

Because detailed notes can become large, they should be **collapsed by default** in the main worklog.

Display:

```text
▸ Detailed Notes
```

Clicking expands the content inline.

No new page should open.

---

# 7.5 Quick Summary

Corresponds to:

```markdown
## 💡 Quick Summary
```

This section captures the user's personal takeaway from the session.

It can describe:

- what was learned;
- what was difficult;
- discoveries;
- mistakes;
- breakthroughs;
- overall progress.

Example:

> I've had a lot of mental blocks that tested my critical thinking and in-depth Python knowledge while implementing the proper logic.

Unlike Activity Breakdown, which answers:

> **What did I do?**

Quick Summary answers:

> **How did the work go, and what did I learn?**

---

# 7.6 Total Time

The Markdown currently contains both:

```yaml
hours: 6
```

and:

```markdown
* Total time invested: **6 hours**.
```

The web application should **not store these separately.**

`hours` should be the source of truth.

When generating Markdown, Worklog automatically generates:

```markdown
* Total time invested: **6 hours**.
```

This prevents mismatches where the frontmatter says six hours but the document body says five.

---

# 8. Compact Worklog Presentation

The feed should avoid rendering the entire Markdown document by default.

A six-hour worklog should initially occupy approximately this much space:

```text
SEP 10                                              6H

FastAPI Setup                               ○ IN PROGRESS

Continued to work on my module for complete setup of REST
APIs and making functional handlers with FastAPI in Python.

⚠ Configuration · Server Security · Logging
→ Server Deployment · Backend Development

💡 I've had a lot of mental blocks that tested my critical
   thinking and in-depth Python knowledge.

▸ Detailed Notes                    GitHub · 12 activities
```

This contains nearly all important information while remaining compact.

---

# 9. Progressive Disclosure

The main UX principle should be **progressive disclosure**.

The feed shows important information immediately.

Long information remains collapsed.

### Always visible

```text
Date
Hours
Tracks
Shipped status
Activity Breakdown
Blockers
Next
Quick Summary
```

### Collapsed by default

```text
Detailed Notes
Images
Individual GitHub commits
Pull-request details
Long code blocks
```

This is particularly important because a developer worklog could eventually contain hundreds of entries.

---

# 10. Images

Images belong primarily inside Detailed Notes.

Instead of displaying a screenshot at full width:

```text
Screenshot

┌──────────────────────────────────────────────────┐
│                                                  │
│              LARGE SCREENSHOT                    │
│                                                  │
└──────────────────────────────────────────────────┘
```

display a compact attachment row:

```text
▣ server-config.png   ▣ api-response.png   +2
```

or:

```text
📎 4 screenshots
```

Clicking opens an image viewer.

Pasting an image directly into the Markdown editor should automatically upload it and insert the corresponding Markdown reference.

---

# 11. GitHub Integration

GitHub activity should be **embedded directly into each daily worklog**, rather than having its own major application section.

Example:

```text
Sep 10 · FastAPI Setup · 6h

Continued working on the REST API...

GitHub
github/worklog-api · 8 commits · 1 PR

▸ Show GitHub activity
```

Expanded:

```text
GitHub · worklog-api

09:32  81fa72  Configure FastAPI logging
10:14  a40bc1  Add authentication handler
11:03  993ae4  Fix middleware configuration
13:41  f31c82  Add request validation
...
```

The application should determine relevant GitHub activity primarily using the worklog date.

This keeps the GitHub integration subordinate to the journal rather than turning Worklog into a GitHub dashboard.

---

# 12. Single-Page Architecture

All major interactions should happen on the same HTML page.

```text
/
│
├── Header
│
├── Quick controls
│
├── Worklog composer
│
└── Worklog feed
      │
      ├── September 17
      ├── September 16
      ├── September 15
      └── ...
```

Interactions such as editing should use:

- inline expansion;
- modals;
- popovers;
- drawers where necessary.

They should **not require separate routes** such as:

```text
/projects
/github
/calendar
/analytics
/entries/123
```

The browser URL can remain simply:

```text
/
```

Optional query/hash state may still be used:

```text
/?date=2026-09
/?track=FastAPI
/#2026-09-10
```

without turning those states into separate application pages.

---

# 13. Minimal Header

Because navigation is unnecessary, the header can be extremely small:

```text
WORKLOG                                      ● GitHub
```

Or:

```text
WORKLOG        2026 · 428h · 137 logs             ⚙
```

The settings button can open a modal.

GitHub configuration can also live inside that modal.

This preserves the one-page philosophy.

---

# 14. Lightweight Filtering

Filtering can sit directly above the worklog:

```text
2026    All Tracks ⌄    Search worklogs...           +
```

Selecting a track:

```text
2026    FastAPI Setup ×    Search...                  +
```

No separate search page is necessary.

Search results simply filter the existing timeline.

---

# 15. Recommended Final Page Structure

The resulting product should essentially be:

```text
┌───────────────────────────────────────────────────────────────┐
│ WORKLOG                                      GitHub ●    ⚙    │
│                                                               │
│ 2026      All Tracks ⌄      Search...                   + Log │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│ SEPTEMBER                                                     │
│                                                               │
│ 10 SEP                                                  6H    │
│ FastAPI Setup                                  ○ IN PROGRESS  │
│                                                               │
│ Continued to work on my module for complete setup of REST     │
│ APIs and making functional handlers with FastAPI in Python.   │
│                                                               │
│ ⚠ Configuration · Server Security · Logging                   │
│ → Server Deployment · Backend Development                     │
│                                                               │
│ 💡 I've had a lot of mental blocks that tested my critical    │
│    thinking and in-depth Python knowledge...                   │
│                                                               │
│ ▸ Detailed Notes                              GitHub · 8       │
│                                                               │
│ ───────────────────────────────────────────────────────────── │
│                                                               │
│ 09 SEP                                                  4H    │
│ Backend Development                                ● SHIPPED  │
│                                                               │
│ Implemented database models and completed initial...          │
│                                                               │
│ ▸ Detailed Notes                              GitHub · 12      │
│                                                               │
│ ───────────────────────────────────────────────────────────── │
│                                                               │
│ 08 SEP                                                  3H    │
│ ...                                                           │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

The result is closer to a **developer's public/private lab notebook** than a productivity dashboard.

---

# 16. Revised Product Definition

The product should now be defined as:

> **Worklog is a single-page developer journal that turns structured Markdown notes and GitHub activity into a compact chronological history of what you built, learned, struggled with, and plan to work on next.**

The `.md` format remains important because the application should ideally treat Markdown as a **portable representation of the user's data**, rather than locking journal entries into a proprietary format.

The relationship should therefore be:

```text
                    WORKLOG ENTRY
                         │
             ┌───────────┴───────────┐
             │                       │
        Web Interface          Markdown (.md)
             │                       │
             └───────────┬───────────┘
                         │
                    Same Data
```

A worklog created through the web interface should be exportable into essentially the same `.md` structure, and an existing `.md` worklog following the schema should eventually be importable back into the application.