Generate the org chart viewer and validate the resulting graph for errors.

Arguments: $ARGUMENTS (optional flags: "fix" to auto-fix issues without prompting)

## Steps

1. Run: `sl-ot-tools generate-viewer`
2. Read the generated `{{COMPANY_DIR}}/org_chart_viewer.html`
3. Extract the embedded `__EMBEDDED_ORG_DATA__` JSON from the HTML
4. If the embedded data is missing or null, stop with an error — the viewer won't work

## Validation

Run these checks against the embedded org chart data:

### 5. Company name resolution
- Check that `data.company` or `data.meta.company.name` resolves to a non-empty string
- If not, warn: "Company name not found — viewer may not display internal people"

### 6. Name consistency: reports_to / dotted_to references
For each person in `leadership`, `people`, and `team` arrays:
- Compute the `makeId` of their `reports_to` value (strip trailing parenthetical like `(inferred)` first)
- Check if that ID matches any person's name ID
- Collect all mismatches (e.g. `reports_to: "Gopikrishna Jandhyala"` but actual name is `"Gopikrishna (Gopi) Jandhyala"`)
- Do the same for `dotted_to`

`makeId` logic: lowercase, replace non-alphanumeric runs with `_`, strip leading/trailing `_`

### 7. Registry RACI name validation
If `{{COMPANY_DIR}}/engagement_registry.json` exists:
- For each engagement and workstream, check each RACI name (R/A/C/I) resolves to a person node ID via `makeId()`
- Collect mismatches
If no registry but `key_programs` exists, fall back to checking `key_altera_contacts` names

### 8. Orphan detection
- Count people with no `reports_to` or whose `reports_to` doesn't resolve to a person
- These will appear as disconnected nodes (not necessarily wrong, but worth flagging)

### 9. Registry validation
- Run `sl-ot-tools validate-registry` (or read `{{COMPANY_DIR}}/engagement_registry.json` directly)
- Check RACI name resolution against org chart
- Flag orphan engagements (in registry but no engagement dir) and orphan workstreams (in config but not registry)

## Report

10. Present a summary:
    - Total people, external orgs, workstreams, engagements
    - Valid reporting edges vs dangling edges
    - Any name mismatches found (with suggested corrections)
    - Orphan nodes
    - RACI name mismatches and orphan workstreams

## Fix

11. If there are name mismatches and the user passed "fix" or confirms when prompted:
    - For each `reports_to` / `dotted_to` mismatch, update the value in `{{COMPANY_DIR}}/org_chart.json` to match the person's actual name
    - For RACI name mismatches in `{{COMPANY_DIR}}/engagement_registry.json`, update names to match the person's actual name
    - Show the changes as a diff before writing
    - After fixing, re-run `sl-ot-tools generate-viewer` to regenerate with corrected data

12. If there are orphan workstreams or engagements, list them but do NOT auto-fix (these require manual review)

13. Final confirmation: open the viewer path for the user
    - `{{COMPANY_DIR}}/org_chart_viewer.html`
