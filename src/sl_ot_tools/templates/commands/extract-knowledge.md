Extract project knowledge from recent emails and append to per-workstream KNOWLEDGE_LOG.md files.

Arguments: $ARGUMENTS should be the number of days to look back (default: 7). Flags:
- "reprocess" — ignore the checkpoint and rescan all emails
- "review" — walk through each email's extractions one-by-one for individual accept/edit/skip/reclassify decisions (instead of presenting a grouped summary)

The knowledge extractor is Claude-driven (not a Python script). Classification and extraction happen inline as you read each email.

{{ENGAGEMENT_RESOLUTION}}

## Setup

1. Parse arguments for days (default 7), whether to reprocess, and whether to use review mode
2. Run the email reader: `sl-ot-read-emails --days <N> --skip-inline`
3. Capture the output directory path (last line of output)
4. Read `index.json` from the output directory
5. Read `<engagement>/engagement_config.json` for workstream classification rules
6. Read `.local/knowledge_checkpoint.json` if it exists (skip if reprocessing)
7. Read `{{COMPANY_DIR}}/engagement_registry.json` to resolve workstream membership via RACI contacts
8. Read the org chart at `{{COMPANY_DIR}}/org_chart.json` for people context

## Status email auto-detection

Before the main extraction loop, auto-detect recurring email patterns that indicate status updates:

1. Group all loaded emails by sender domain + normalized subject pattern:
   - Strip dates, numbers, "RE:", "FW:" prefixes from subjects
   - Group emails with the same sender address AND >80% similar normalized subject
2. Flag groups with **3+ occurrences** as "recurring status pattern"
3. If any recurring patterns are detected, present them to the user:

```
Detected recurring status emails:
1. Deloitte (sarah.jones@deloitte.com) — "Weekly Status Update - Enclave" (8 emails)
   → Suggested workstream: enclave/background
   → Suggested type: STATUS
2. NCC Group (reports@ncc.com) — "Cyber Assessment Progress" (4 emails)
   → Suggested workstream: cyber/general
   → Suggested type: STATUS
```

4. For each pattern, ask the user to **Confirm** (accept routing), **Adjust** (change workstream), or **Ignore** (treat as normal emails)
5. Confirmed patterns: all matching emails get classified as STATUS type and routed to the confirmed workstream — they skip the normal classification step
6. Remaining (non-pattern) emails proceed through normal classification below

## Filtering

- Skip emails whose subject+date key is already in the checkpoint (unless reprocessing)
- Skip emails whose sender matches any pattern in skip_senders (merged from platform defaults + company + engagement configs)
- After filtering, report how many emails remain to process (and how many were skipped)

## Attachment triage

For emails within the last **7 days** that have attachments (office files: .docx, .pptx, .xlsx, .pdf):

1. After filtering but before classification, scan remaining emails for attachments
2. For each email with office-file attachments, show the attachment list:
   ```
   Email: "Q4 Status Update" from sarah.jones@deloitte.com
   Attachments:
     - [pptx] Enclave Status Deck.pptx (245 KB)
     - [xlsx] Budget Tracker.xlsx (89 KB)
   Process these for document knowledge? [Yes / Skip]
   ```
3. If **Yes**: add each attachment to `{{COMPANY_DIR}}/file_index.json` with:
   - `source: "email_attachment"`
   - `email_id`, `email_subject`, `original_name` from the email
   - `is_primary: true` (unless a duplicate hash already exists)
   Also add the relative path to `{{COMPANY_DIR}}/doc_triage.json` approved list
4. If **Skip**: move on, don't add to file index
5. Accepted attachments will be extracted and knowledge-processed in the next `/extract-doc-knowledge` run

This keeps the two pipelines connected — email review surfaces attachments, document pipeline processes them.

## Classification

For each remaining email, read its body file (`*_body.txt`) and classify it against each workstream in `engagement_config.workstreams`. An email matches a workstream if ANY of:
- Subject or body contains a keyword from that workstream's `keywords_subject` or `keywords_body` (case-insensitive)
- Sender or any recipient email address is in that workstream's `people_associations`
- Sender or any recipient is in the RACI for a workstream in `engagement_registry.json` (cross-reference via registry RACI contacts)

An email can match multiple workstreams. If it matches none, skip it silently.

## Extraction

For each classified email, extract knowledge nuggets. A nugget has:
- **type**: one of the `knowledge_types` from config (decision, technical, status, action, blocker, timeline, budget, risk)
- **summary**: one-line summary of the nugget
- **workstreams**: which workstreams from the engagement registry this relates to (array, format: `engagement/workstream`)
- **detail**: 1-3 sentences of context
- **email_id**: the email's ID from index.json

An email may yield 0 nuggets (routine/FYI with no extractable knowledge) or multiple nuggets.

## Default mode (summary)

8. Process all emails, collect all nuggets grouped by workstream
9. Present findings:
   - Total emails processed, total nuggets extracted, breakdown by workstream
   - For each workstream: list nuggets grouped by type, showing summary + detail
10. Ask what to do:
    - **Append all** — write all nuggets to KNOWLEDGE_LOG.md files
    - **Review first** — switch to review mode for individual decisions
    - **Skip** — discard everything, update checkpoint only

## Review mode (when "review" flag is present)

8. Show overall stats first (emails to process, workstreams detected)
9. Walk through each email **one at a time**. For each email, show:
   - Subject, sender, date, matched workstreams
   - Extracted nuggets (type, summary, detail, workstreams)
10. For each email's nuggets, ask:
    - **Accept** — append these nuggets as-is
    - **Edit** — let me modify the nuggets (change type, summary, detail, workstreams, or split/merge)
    - **Skip** — don't append, but still mark as processed in checkpoint
    - **Reclassify** — change which workstreams this email maps to, then re-present
11. After all emails are reviewed, show final summary of accepted nuggets before writing

## Writing to KNOWLEDGE_LOG.md

For each workstream with accepted nuggets:
- Resolve the output path: `<engagement>/<workstream.output_dir>/KNOWLEDGE_LOG.md`
- If the file doesn't exist, create it with this header:

```markdown
# Knowledge Log — <workstream.label>

Append-only record of project knowledge extracted from email. Each entry is dated and categorized.
Entries are added by `/extract-knowledge` and should not be manually reordered or deleted.

---
```

- Append a dated section if one doesn't already exist for today:

```markdown
## 2026-02-15
```

- Append each nugget in this format:

```markdown
### [TYPE] Summary line here
- **Source**: "Subject line" (Sender Name → Recipient Name)
- **Workstreams**: enclave/hybrid_poc, cyber/general
- **Detail**: 1-3 sentences of extracted context.
- **Email ID**: `abc123def456`
```

- TYPE is uppercased (e.g., DECISION, TECHNICAL, STATUS, ACTION, BLOCKER, TIMELINE, BUDGET, RISK)

## Checkpoint update

After writing (or skipping), update `.local/knowledge_checkpoint.json`:
- Use subject+date dedup keys (not email IDs) for cross-user compatibility
- Format: `{"last_updated": "...", "processed": [{"key": "normalized_subject|date", "subject": "...", "date": "..."}]}`
- Add all processed emails to the checkpoint
- Update `last_updated` timestamp

## Important notes

- Multi-workstream emails: write nuggets to each matching workstream's log. The email ID provides cross-log traceability.
- Do NOT extract knowledge from emails that are purely scheduling (meeting invites, calendar updates) unless they contain substantive decisions or context.
- When in doubt about a nugget's type, prefer "status" as the default.
- Read body files for full context — don't classify based on subject line alone.

## Examples

- `/extract-knowledge` — last 7 days, summary mode
- `/extract-knowledge 14 review` — last 14 days, one-by-one review
- `/extract-knowledge 30` — last 30 days, summary mode
- `/extract-knowledge reprocess` — rescan all cached emails, ignoring checkpoint
- `/extract-knowledge 7 reprocess review` — rescan last 7 days, review each one
