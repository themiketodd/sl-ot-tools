Generate a current-state PROJECT_BRIEF.md for one or more workstreams by synthesizing their KNOWLEDGE_LOG.md.

Arguments: $ARGUMENTS should be a workstream slug (from engagement_config.json) or `all` (default: `all`).

## Setup

1. Parse arguments for which workstream(s) to brief
2. Read `{{ENGAGEMENT_DIR}}/engagement_config.json` to resolve workstream paths
3. Read the org chart at `{{COMPANY_DIR}}/org_chart.json` for program context

## For each requested workstream

4. Resolve the knowledge log path: `{{ENGAGEMENT_DIR}}/<workstream.output_dir>/KNOWLEDGE_LOG.md`
5. If the log doesn't exist, report "No knowledge log found for <workstream.label>" and skip
6. Read the full KNOWLEDGE_LOG.md
7. Read the org chart's `key_programs` section for programs listed in the workstream's config

## Synthesis

Generate a PROJECT_BRIEF.md with these sections:

```markdown
# Project Brief — <workstream.label>

> Auto-generated from KNOWLEDGE_LOG.md by `/project-brief`. Last generated: <date>.
> This file is regenerated on each run — do not edit manually.

---

## Current Status
One paragraph summarizing where the project stands right now, based on the most recent STATUS and DECISION entries.

## Key Decisions
Bulleted list of all DECISION entries, most recent first. Include date and source.

## Open Blockers
Bulleted list of BLOCKER entries that have NOT been resolved by a later DECISION or STATUS entry. If none, write "No open blockers identified."

## Active Action Items
Bulleted list of ACTION entries that have NOT been superseded or completed per later entries. Include who owns them if mentioned. If none, write "No active action items identified."

## Technical Architecture
Summary of TECHNICAL entries — what's been decided about architecture, tools, infrastructure, integrations. Synthesize into a coherent narrative rather than listing raw entries.

## Timeline & Milestones
Consolidation of TIMELINE entries. List known dates, deadlines, and milestones chronologically.

## Budget & Cost
Consolidation of BUDGET entries. List known figures, estimates, and cost decisions. If none, write "No budget information captured."

## Risk Register
Bulleted list of RISK entries that remain relevant. If none, write "No risks identified."

## Recent Activity (Last 14 Days)
Chronological list of ALL entries from the last 14 days, regardless of type. Format:
- **<date>** [TYPE] Summary — Detail snippet

## Knowledge Coverage
Stats table:
| Metric | Value |
|--------|-------|
| Total entries | N |
| Date range | earliest — latest |
| Entry types | breakdown by type |
| Programs referenced | list |
| Unique email sources | N |
```

## Writing

8. Write the brief to `{{ENGAGEMENT_DIR}}/<workstream.output_dir>/PROJECT_BRIEF.md`, replacing any existing file
9. Report what was generated: workstream name, entry count, date range, any notable gaps

## When generating for `all`

Process each workstream from engagement_config.json. Report a combined summary at the end showing which workstreams had logs, entry counts, and any workstreams with no log yet.

## Important notes

- The brief is a **regenerated view**, not an append-only log. It replaces the previous brief entirely.
- Resolve contradictions by favoring more recent entries (later dates win).
- For "Open Blockers" and "Active Action Items", use your judgment about whether later entries resolve earlier ones. When in doubt, keep the item as open.
- Don't fabricate information — only include what's in the knowledge log.
- If a section has no relevant entries, include the section header with a "None captured" note rather than omitting it.
