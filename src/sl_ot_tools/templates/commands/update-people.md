Scan recent emails and update the organizational intelligence people data.

Arguments: $ARGUMENTS should be the number of days to look back (default: 7). Flags:
- "reprocess" — ignore the checkpoint and rescan all emails
- "review" — walk through each proposed update one-by-one for individual accept/skip/ignore decisions (instead of presenting a summary)

The people processor is config-driven. Settings are auto-discovered:
- Company config: `_company/company_config.json` (domains, labels, patterns, hints)
- People config: `_company/people_config.json` (org chart, checkpoint, ignore list paths)

1. Parse arguments for days (default 7), whether to reprocess, and whether to use review mode
2. Run the email reader: `sl-ot-read-emails --days <N> --skip-inline`
3. Capture the output directory path (last line of output)
4. Run the people processor: `sl-ot-process-people <output_dir>` (add `--reprocess` if requested)
5. Read the generated `people_report.json` from the output directory

## Default mode (summary)

6. Present findings:
   - Summary stats (emails processed, new people, known people activity)
   - For each **new person**: name, email, org, title (if extracted), email subjects they appeared in
   - For **known people**: activity level, new subjects
7. Ask what I'd like to do:
   - Add new people to the org chart (at `{{COMPANY_DIR}}/org_chart.json`)
   - Update signals for existing people
   - Ignore specific people permanently (adds them to `{{COMPANY_DIR}}/people_ignore.json`)
   - Do nothing
8. If ignoring people, read or create `{{COMPANY_DIR}}/people_ignore.json` and add their email addresses to the `ignored` array with a `reason` note
9. If updating the org chart, read the current JSON, make proposed changes, and show me a diff before writing

## Review mode (when "review" flag is present)

6. Show summary stats first (emails processed, total new people, total known people with activity)
7. Then walk through each person **one at a time**, starting with new people, then known people with signals. For each person, present:
   - Name, email, org, title (if extracted)
   - Email subjects they appeared in
   - For known people: current org chart entry vs new signals detected
8. After presenting each person, ask what to do with **this specific person**:
   - **Add/Update** — add to org chart (new person) or update their signals (known person)
   - **Skip** — leave unchanged for now (will appear again next run)
   - **Ignore** — add to ignore list permanently (won't appear in future scans)
9. Collect all decisions, then apply them in a single batch:
   - Add accepted new people to the org chart
   - Update signals for accepted known people
   - Add ignored people to `{{COMPANY_DIR}}/people_ignore.json`
   - Show a final diff of all org chart changes before writing
10. Confirm before writing changes
