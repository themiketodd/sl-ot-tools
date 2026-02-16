# sl-ot-tools

Silver Lake Operating Technology tools for portfolio company engagement management.

A pip-installable package that provides tools for syncing with SharePoint, extracting intelligence from Outlook email, managing organizational data, converting Markdown to Word, and generating interactive org chart viewers. Designed for use with Claude Code — skills (slash commands) are installed per-repo.

---

## Quick Start (From Zero)

### Prerequisites

- Python 3.9+
- pip
- git
- Claude Code
- WSL2 if on Windows (for SharePoint sync via OneDrive, Outlook email extraction)
- Outlook desktop app (for email extraction — uses MAPI COM)

### Install the tools

```bash
pip install sl-ot-tools
```

This puts the following commands on your PATH:

| Command | Purpose |
|---|---|
| `sl-ot-tools` | CLI for init, setup, check, viewer generation |
| `sl-ot-sync` | Bidirectional sync with SharePoint via OneDrive |
| `sl-ot-read-emails` | Extract emails from Outlook into structured JSON |
| `sl-ot-process-people` | Scan email exports for organizational intelligence |
| `sl-ot-md2docx` | Convert Markdown files to Word documents |

### Set up a new portfolio company

```bash
sl-ot-tools init company acme
cd acme
```

This scaffolds:

```
acme/
├── _company/
│   ├── company_config.json    # Domains, labels, skip patterns
│   ├── people_config.json     # Paths to org chart, checkpoint, ignore list
│   ├── org_chart.json         # Empty — seed with known leadership
│   ├── people_checkpoint.json # Empty
│   └── people_ignore.json     # Empty
├── .claude/commands/          # Skills installed by setup
├── .gitignore
└── CLAUDE.md
```

Edit `_company/company_config.json` with the company's domains and conventions:

```json
{
  "company": "Acme",
  "domains": ["acme.com", "vendor.com"],
  "domain_labels": { "acme.com": "Acme", "vendor.com": "Vendor" },
  "skip_senders": ["noreply@acme.com"],
  "contractor_patterns": ["^[a-z]+x\\."],
  "location_hints": ["San Jose", "New York", "London"]
}
```

### Add an engagement

```bash
sl-ot-tools init engagement deal-evaluation
```

This creates:

```
deal-evaluation/
├── engagement_config.json     # Workstreams, keywords, people associations
├── sync-map.conf              # SharePoint folder mappings (no hardcoded roots)
├── sync_to_sharepoint.sh      # Wrapper: exec sl-ot-sync push
├── sync_from_sharepoint.sh    # Wrapper: exec sl-ot-sync pull
└── 01-General/                # Default workstream directory
```

Edit `engagement_config.json` to define workstreams with classification rules:

```json
{
  "engagement": "deal-evaluation",
  "engagement_label": "Deal Evaluation",
  "knowledge_types": ["decision", "technical", "status", "action", "blocker", "timeline", "budget", "risk"],
  "skip_senders": [],
  "workstreams": {
    "diligence": {
      "label": "01-Diligence",
      "output_dir": "01-Diligence",
      "keywords_subject": ["due diligence", "DD", "financials"],
      "keywords_body": ["due diligence", "financial model"],
      "programs": ["tech_dd"],
      "people_associations": ["analyst@acme.com"]
    }
  }
}
```

Edit `sync-map.conf` to map local dirs to SharePoint folders:

```conf
# LOCAL_ROOT: auto-resolved from this file's parent directory
# REMOTE_ROOT: resolved from .local/user-config.json

01-Diligence | Diligence | Due Diligence workstream
push:file:../_company/org_chart.json | People | Org Chart JSON (push-only)
push:file:../_company/org_chart_viewer.html | People | Org Chart Viewer (push-only)
```

### Run interactive setup

```bash
sl-ot-tools setup
```

This prompts for:
- **User name** (your identity for checkpoints)
- **OneDrive root path** (e.g., `/mnt/c/Users/jane.doe/OneDrive - Silver Lake/OT Sharepoint Shortcuts`)
- **SharePoint path** for each engagement (e.g., `Companies/Acme/Deal Evaluation`)

Then automatically:
- Creates `.local/user-config.json` (gitignored, per-user)
- Installs Claude Code skills to `.claude/commands/`
- Generates org chart viewer HTML
- Runs verification checks

### Push to GitHub

```bash
git init && git add -A && git commit -m "Initial company repo"
gh repo create --private themiketodd/acme --source . --push
```

Company repos should be private — access is controlled per-company.

---

## Onboarding (Associate Joining an Existing Company)

What the associate needs from the Operating Partner:
1. GitHub repo URL
2. SharePoint folder path per engagement

What the associate needs installed: Python 3.9+, pip, git, Claude Code. WSL2 if on Windows.

```bash
pip install sl-ot-tools                   # 1. One-time tool install
git clone <company-repo-url> && cd acme   # 2. Clone company repo
sl-ot-tools setup                         # 3. Interactive local config
```

`sl-ot-tools setup` handles everything: prompts for OneDrive paths, installs skills, generates viewer.

---

## Architecture

```
sl-ot-tools (pip package)          Company repo (git)
  Tools on PATH                      _company/     ← company-level data
  Skill templates                    <engagement>/  ← per-engagement data
  Viewer template                    .local/        ← per-user config (gitignored)
  Config resolver                    .claude/commands/ ← installed skills
  Platform defaults
```

### Two-repo design

**`sl-ot-tools`** is a generic, reusable package — no company-specific data. Installed once via pip, shared across all company repos.

**Company repos** (one per portfolio company) contain company-level data (`_company/`) and engagement directories. Company repos are private, access-controlled per company.

### Config hierarchy

Configuration merges three levels:

1. **Platform defaults** (in sl-ot-tools) — standard skip_senders (Zoom, GitHub, AWS, etc.)
2. **Company config** (`_company/company_config.json`) — company-specific domains, patterns, locations
3. **Engagement config** (`<engagement>/engagement_config.json`) — workstream keywords, people, skip_senders

### Data ownership

| Data | Location | Shared? |
|---|---|---|
| Org chart | `_company/org_chart.json` | Yes (committed) |
| People checkpoint | `_company/people_checkpoint.json` | Yes (committed) |
| People ignore list | `_company/people_ignore.json` | Yes (committed) |
| Company config | `_company/company_config.json` | Yes (committed) |
| Engagement config | `<engagement>/engagement_config.json` | Yes (committed) |
| Knowledge logs | `<engagement>/<workstream>/KNOWLEDGE_LOG.md` | Yes (committed) |
| User config | `.local/user-config.json` | No (gitignored) |
| Knowledge checkpoint | `.local/knowledge_checkpoint.json` | No (gitignored) |
| Email output | `.local/email_output/` | No (gitignored) |

### Path resolution

Tools auto-discover their context by walking up the filesystem:
- **Repo root**: First directory containing `_company/`
- **Company dir**: `<repo_root>/_company/`
- **Engagement dir**: First ancestor containing `engagement_config.json`
- **Local dir**: `<repo_root>/.local/`
- **Sync roots**: LOCAL_ROOT from conf file's parent; REMOTE_ROOT from `.local/user-config.json`

Environment variable overrides: `SL_OT_LOCAL_ROOT`, `SL_OT_REMOTE_ROOT`.

---

## Tools Reference

### Sync Engine (`sl-ot-sync`)

Config-driven bidirectional sync between local repo and SharePoint via OneDrive.

**sync-map.conf format**:
```conf
# Lines: LOCAL_PATH | REMOTE_PATH | LABEL
# Prefixes: push: (local→SharePoint only), pull: (SharePoint→local only), file: (single file)
# No prefix = bidirectional

01-Background/Data | Data from Company | Data drops
push:file:../_company/org_chart.json | People | Org Chart (push-only)
pull:03-Reports | Reports | Reports from team
```

- LOCAL_ROOT auto-resolved from conf file's parent directory
- REMOTE_ROOT resolved from `.local/user-config.json` (OneDrive root + engagement mapping)
- Pull uses `--ignore-existing` (won't overwrite local work)
- Push uses `--update` (only copies newer files)
- Logs to `.local/sync_logs/`

**Usage** (via engagement wrapper scripts):
```bash
./sync_to_sharepoint.sh --dry-run    # Preview push
./sync_to_sharepoint.sh              # Push local → SharePoint
./sync_from_sharepoint.sh --dry-run  # Preview pull
./sync_from_sharepoint.sh            # Pull SharePoint → local
```

### Email Reader (`sl-ot-read-emails`)

PowerShell-based Outlook extractor (MAPI COM) with a bash wrapper for WSL.

Extracts: sender, recipients, subject, timestamps, plain text + HTML bodies, attachments. Output: structured `index.json` + individual body/attachment files.

Output is ephemeral — written to `.local/email_output/<timestamp>/`, auto-cleaned to last 3 runs.

```bash
sl-ot-read-emails --days 14 --skip-inline
```

### People Processor (`sl-ot-process-people`)

Scans email exports for organizational intelligence. Cross-references configured domains, extracts signatures for titles/locations, identifies new people and activity signals for known people.

- Auto-discovers `_company/people_config.json` and `company_config.json`
- Merges domains, labels, contractor patterns, and location hints from company config
- Tracks processed emails via `_company/people_checkpoint.json` (committed, shared)
- Produces `people_report.json` in the email output directory

```bash
sl-ot-process-people <email_output_dir>
sl-ot-process-people <email_output_dir> --reprocess  # Ignore checkpoint
```

### Knowledge Extractor (Claude-driven)

Not a standalone script — this is a Claude Code skill (`/extract-knowledge`). Claude reads email bodies inline, classifies them against workstream rules, and extracts structured knowledge nuggets.

**Classification**: An email matches a workstream if ANY of:
- Subject or body contains a keyword (case-insensitive)
- Sender or recipient is in the workstream's `people_associations`
- Sender or recipient is a key contact for a program in the workstream's `programs` (cross-reference via org chart)

Multi-workstream emails write to each matching log. Email IDs provide cross-log traceability.

**Knowledge types**: decision, technical, status, action, blocker, timeline, budget, risk.

**Checkpoint**: Per-user at `.local/knowledge_checkpoint.json` (gitignored). Uses subject+date dedup keys (not email IDs) for cross-user compatibility — different Outlook accounts have different EntryIDs for the same email.

**Output format** (in KNOWLEDGE_LOG.md):
```markdown
## 2026-02-15

### [DECISION] Summary line
- **Source**: "Subject" (Sender → Recipient)
- **Programs**: program_a, program_b
- **Detail**: 1-3 sentences of context.
- **Email ID**: `abc123def456`
```

**Two-file pattern** per workstream:
- `KNOWLEDGE_LOG.md` — Append-only dated entries. The permanent record.
- `PROJECT_BRIEF.md` — Regenerated current-state summary. The readable view.

### Document Generator (`sl-ot-md2docx`)

Converts Markdown files to formatted Word documents (.docx).

Supports: headings, bold/italic, tables, nested lists, code blocks, blockquotes, footnotes, LaTeX math, horizontal rules, links.

```bash
sl-ot-md2docx analysis.md                    # → analysis.docx
sl-ot-md2docx analysis.md output/report.docx  # Explicit output path
```

### Org Chart Viewer (`sl-ot-tools generate-viewer`)

Generates a self-contained HTML viewer from `_company/org_chart.json`. Uses Cytoscape.js with fcose layout.

- Loads `org_chart.json` via `fetch()` (no baked-in data)
- Sidebar filters for organizations and programs
- Node size slider, pan/zoom, node dragging
- 5 edge types: reporting, internal, subgraph, affiliation, program
- Re-layout button and keyboard shortcuts

```bash
sl-ot-tools generate-viewer  # Regenerates _company/org_chart_viewer.html
```

---

## Claude Code Skills

Skills are installed to `.claude/commands/` by `sl-ot-tools setup`. They chain the tools above into higher-level workflows invoked via `/command` in Claude Code.

| Skill | Purpose |
|---|---|
| `/sync-push` | Push local files to SharePoint (dry-run first) |
| `/sync-pull` | Pull latest from SharePoint (dry-run first) |
| `/read-emails [days]` | Extract and summarize recent Outlook emails |
| `/update-people [days] [flags]` | Scan emails for people signals, update org chart |
| `/extract-knowledge [days] [flags]` | Classify emails, extract knowledge to KNOWLEDGE_LOG.md |
| `/project-brief [workstream\|all]` | Regenerate PROJECT_BRIEF.md from knowledge log |
| `/md2docx [file]` | Convert Markdown to Word, offer to sync |

### Flags

`/update-people` and `/extract-knowledge` accept:
- `reprocess` — Ignore checkpoint, rescan all cached emails
- `review` — Walk through each item one-by-one (instead of grouped summary)

Examples:
```
/extract-knowledge 14 review     # 14 days, review each email
/update-people reprocess         # Rescan all, summary mode
/extract-knowledge 7 reprocess review  # 7 days, rescan all, review each
```

---

## Workflows

### Weekly Intelligence Cycle (Operating Partner)

```
/read-emails 7              → Extract recent emails
/update-people 7            → Discover new contacts → update org chart
/extract-knowledge 7        → Extract workstream knowledge → KNOWLEDGE_LOG.md
/project-brief all          → Regenerate PROJECT_BRIEF.md per workstream
/sync-push                  → Push updated files to SharePoint
git add ... && git commit && git push  → Share via git
```

### Creating a Deliverable

```
1. Write analysis in Markdown (git-tracked)
2. /md2docx analysis.md      → Convert to Word
3. /sync-push                 → Push .docx to SharePoint
4. git commit                 → Commit the Markdown source
```

### Pulling in New Data

```
/sync-pull                    → Pull latest from SharePoint
                              → Review new files
                              → Commit text files to git
```

### Daily Operations

```
git pull                               # Get latest from team
cd <engagement> && ./sync_from_sharepoint.sh  # Pull latest from SharePoint
# ... work (analysis, documents, Claude Code skills) ...
./sync_to_sharepoint.sh                # Push deliverables to SharePoint
git add <files> && git commit && git push  # Share via git
```

---

## Adding a New Engagement to an Existing Company

```bash
cd ~/code/acme
sl-ot-tools init engagement value-creation-2027
# Edit value-creation-2027/engagement_config.json (workstreams, keywords, people)
# Edit value-creation-2027/sync-map.conf (SharePoint folder mappings)
sl-ot-tools setup   # Detects new engagement, prompts for SharePoint path
git add value-creation-2027/ .claude/commands/ && git commit && git push
```

---

## Setting Up a New Portfolio Company

```bash
pip install sl-ot-tools  # If not already installed
sl-ot-tools init company acme && cd acme
# Edit _company/company_config.json (domains, labels, skip patterns)
# Seed _company/org_chart.json with known leadership
sl-ot-tools init engagement deal-evaluation
# Edit deal-evaluation/engagement_config.json (workstreams, keywords)
# Edit deal-evaluation/sync-map.conf (SharePoint folder mappings)
sl-ot-tools setup
git init && git add -A && git commit -m "Initial repo"
gh repo create --private themiketodd/acme --source . --push
```

---

## Config Formats

### `.local/user-config.json` (per-user, gitignored)

```json
{
  "user": "michael.todd",
  "onedrive_root": "/mnt/c/Users/michael.todd/OneDrive - Silver Lake/OT Sharepoint Shortcuts",
  "onedrive_mappings": {
    "enclave": "Companies/Altera/Enclave",
    "value-creation": "Companies/Altera/Value Creation"
  }
}
```

### `_company/company_config.json`

```json
{
  "company": "Altera",
  "domains": ["altera.com", "intel.com", "deloitte.com"],
  "domain_labels": { "altera.com": "Altera", "intel.com": "Intel" },
  "skip_senders": ["noreply@altera.com"],
  "contractor_patterns": ["^[a-z]+x\\."],
  "location_hints": ["San Jose", "Santa Clara", "Penang"]
}
```

### `_company/people_config.json`

```json
{
  "org_chart": "org_chart.json",
  "checkpoint": "people_checkpoint.json",
  "ignore_list": "people_ignore.json"
}
```

### `<engagement>/engagement_config.json`

```json
{
  "engagement": "enclave",
  "engagement_label": "Enclave Move",
  "knowledge_types": ["decision", "technical", "status", "action", "blocker", "timeline", "budget", "risk"],
  "skip_senders": [],
  "workstreams": {
    "background": {
      "label": "01-Background",
      "output_dir": "01-Background",
      "keywords_subject": ["org chart", "leadership"],
      "keywords_body": ["organizational structure"],
      "programs": ["it_separation"],
      "people_associations": ["craig.leclair@altera.com"]
    }
  }
}
```

### `<engagement>/sync-map.conf`

```conf
# LOCAL_ROOT: auto-resolved from this file's parent directory
# REMOTE_ROOT: resolved from .local/user-config.json
#
# Format: LOCAL_PATH | REMOTE_PATH | LABEL
# Prefixes: push: (push-only), pull: (pull-only), file: (single file)

01-Background/Data | Data from Company | Company data drops
push:file:../_company/org_chart.json | People | Org Chart JSON
```

---

## Conventions

- **Text files in git, binaries in SharePoint.** The sync engine bridges them.
- **Org chart JSON is source of truth.** The viewer HTML is derived from it.
- **Email output is ephemeral.** Never committed to git. Auto-cleaned to last 3 runs.
- **Skills are composable.** `/read-emails` feeds `/update-people` and `/extract-knowledge`. `/extract-knowledge` feeds `/project-brief`. All feed `/sync-push`.
- **Dry-run first.** Both sync directions preview before executing.
- **Checkpoints for idempotency.** People processor and knowledge extractor each track what they've seen (separate checkpoint files).
- **Append-only knowledge logs.** KNOWLEDGE_LOG.md files are the permanent record — never reorder, edit, or delete entries. PROJECT_BRIEF.md is the regenerated readable view.
- **People checkpoint committed, knowledge checkpoint per-user.** People data is shared (prevents duplicate org chart entries). Knowledge dedup uses subject+date keys (different Outlook accounts have different email IDs for the same email).

---

## Development

```bash
git clone https://github.com/themiketodd/sl-ot-tools.git
cd sl-ot-tools
pip install -e .   # Editable install
pytest             # Run tests
```

Package structure:
```
src/sl_ot_tools/
├── cli.py              # sl-ot-tools CLI
├── config/
│   ├── defaults.py     # Platform-level defaults
│   └── resolver.py     # Config auto-discovery and merging
├── email/
│   ├── read_email.sh   # Bash wrapper for WSL
│   ├── read_email.ps1  # PowerShell Outlook MAPI extractor
│   ├── process_people.py
│   └── entry.py        # sl-ot-read-emails entry point
├── sync/
│   ├── sync.sh         # rsync-based sync engine
│   └── entry.py        # sl-ot-sync entry point
├── docgen/
│   ├── md2docx.py      # sl-ot-md2docx entry point
│   └── md2docx_renderer.py
├── viewer/
│   └── org_chart_template.html
├── knowledge/
│   └── dedup.py        # Subject+date dedup logic
└── templates/
    └── commands/       # Skill templates (7 files)
```
