Extract project knowledge from document summaries and append to per-workstream KNOWLEDGE_LOG.md files.

Arguments: $ARGUMENTS may include flags:
- "reprocess" — ignore the checkpoint and rescan all summaries
- "review" — walk through each document's extractions one-by-one for individual accept/edit/skip decisions

The document knowledge extractor is Claude-driven (not a Python script). Classification and extraction happen inline as you read each summary.

{{ENGAGEMENT_RESOLUTION}}

## Setup

1. Parse arguments for whether to reprocess and whether to use review mode
2. Read `{{COMPANY_DIR}}/file_index.json` for document metadata
3. Read `<engagement>/engagement_config.json` for workstream classification rules
4. Read `.local/doc_knowledge_checkpoint.json` if it exists (skip if reprocessing)
5. Read `{{COMPANY_DIR}}/engagement_registry.json` to resolve workstream membership via RACI contacts
6. Read the org chart at `{{COMPANY_DIR}}/org_chart.json` for people context
6. Read `{{COMPANY_DIR}}/doc_triage.json` for triage state

## Interactive triage (first-run or new files)

Before extracting knowledge, check for documents that haven't been triaged yet.

1. Load `{{COMPANY_DIR}}/doc_triage.json` (create if missing with empty approved/skipped/skip_patterns)
2. Compare `file_index.json` entries (primary files only) against triage state
3. A file needs triage if it's NOT in approved, NOT in skipped, and NOT matching any skip_pattern
4. If there are untriaged files, present them grouped by engagement/workstream directory:

```
New documents found (12 files):

enclave/03-Hybrid-Infrastructure-PoC/
  1. [pptx] AWS Cost Analysis.pptx (245 KB, Jan 15)
  2. [xlsx] Commitment Ladder.xlsx (89 KB, Jan 20)
  3. [pdf]  Vendor Proposal - NetApp.pdf (1.2 MB, Dec 10)

cyber/01-General/
  4. [pptx] IT Security SCQ.pptx (180 KB, Oct 24)
  ...

For each: [P]rocess / [S]kip / [A]lways skip pattern?
```

5. For each file, ask the user:
   - **Process** — add to `approved` list
   - **Skip** — add to `skipped` list (will ask again next run)
   - **Always skip pattern** — ask for a glob pattern (e.g., `*/Archive/*`, `*SCQ*`), add to `skip_patterns`
6. You can also offer batch options: "Process all in this directory" / "Skip all in this directory"
7. After triage, write updated `doc_triage.json`

## Finding summaries

Look for `_summaries/*.md` files in each engagement's workstream output directories. These are created by `sl-ot-tools extract-text`.

For each summary file:
- Read the YAML front-matter to get `source_file`, `sha256`, `file_type`, `source`
- Use `source_file|sha256` as the dedup key
- Skip if already in the checkpoint (unless reprocessing)

Report how many summaries are available and how many are new.

## Extraction

For each unprocessed summary, read the full markdown content and extract knowledge nuggets. A nugget has:
- **type**: one of the `knowledge_types` from config (decision, technical, status, action, blocker, timeline, budget, risk)
- **summary**: one-line summary of the nugget
- **workstreams**: which workstreams from the engagement registry this relates to (array, format: `engagement/workstream`)
- **detail**: 1-3 sentences of context
- **source_file**: the relative path to the source document

Documents often produce more nuggets per item than emails (a 20-slide deck may yield 5-10 nuggets).

## Default mode (per-document summary)

8. Process all unprocessed summaries
9. For each document, present:
   - Filename, file type, engagement/workstream, nugget count
   - One-line summary for each extracted nugget
10. Ask what to do per document:
    - **Accept all** — write all nuggets from this document
    - **Drill down** — review individual nuggets (accept/edit/skip each)
    - **Skip** — don't write nuggets but mark as processed in checkpoint

## Review mode (when "review" flag is present)

8. Show overall stats first (summaries to process, workstreams detected)
9. Walk through each document **one at a time**. For each document, show:
   - Source filename, file type, workstream
   - Each extracted nugget (type, summary, detail, workstreams)
10. For each nugget, ask:
    - **Accept** — include this nugget
    - **Edit** — modify the nugget (change type, summary, detail, workstreams)
    - **Skip** — don't include this nugget
11. After all documents reviewed, show final summary of accepted nuggets before writing

## Writing to KNOWLEDGE_LOG.md

For each workstream with accepted nuggets:
- Resolve the output path: `<engagement>/<workstream.output_dir>/KNOWLEDGE_LOG.md`
- If the file doesn't exist, create it with this header:

```markdown
# Knowledge Log — <workstream.label>

Append-only record of project knowledge extracted from documents and email. Each entry is dated and categorized.
Entries are added by `/extract-doc-knowledge` and should not be manually reordered or deleted.

---
```

- Append a dated section if one doesn't already exist for today:

```markdown
## 2026-02-19
```

- Append each nugget in this format:

```markdown
### [TYPE] Summary line here
- **Source**: "filename.pptx" (engagement/workstream/)
- **Workstreams**: enclave/hybrid_poc, cyber/general
- **Detail**: 1-3 sentences of extracted context.
- **Source File**: `enclave/03-Hybrid-Infrastructure-PoC/Cost-Analysis/AWS Cost Analysis.pptx`
```

- TYPE is uppercased (e.g., DECISION, TECHNICAL, STATUS, ACTION, BLOCKER, TIMELINE, BUDGET, RISK)

## Checkpoint update

After writing (or skipping), update `.local/doc_knowledge_checkpoint.json`:
- Use file_path+sha256 dedup keys (not email IDs)
- Format: `{"last_updated": "...", "processed": [{"key": "path|hash", "relative_path": "...", "sha256": "...", "filename": "..."}]}`
- Add all processed documents to the checkpoint
- Update `last_updated` timestamp

## Important notes

- Documents can yield many more nuggets than emails — a status deck might have 5+ actionable items
- Cross-reference `engagement_registry.json` RACI contacts to identify which workstreams a document relates to
- When classifying a document to workstreams, use the same rules as email classification but also consider the document's engagement/workstream from the file index
- Do NOT extract knowledge from template files, blank forms, or purely formatting-only content
- When in doubt about a nugget's type, prefer "technical" for content-heavy documents and "status" for updates

## Examples

- `/extract-doc-knowledge` — process new summaries, per-document review
- `/extract-doc-knowledge review` — one-by-one nugget review
- `/extract-doc-knowledge reprocess` — rescan all summaries, ignoring checkpoint
- `/extract-doc-knowledge reprocess review` — rescan all, review each nugget
