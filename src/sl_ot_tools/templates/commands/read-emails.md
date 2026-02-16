Read the last $ARGUMENTS days of emails from Outlook (default: 7 if not specified).

1. Run: `sl-ot-read-emails --days <N> --skip-inline`
2. Read the generated `index.json` from the output directory
3. Provide a summary: total count, grouped by sender, key subjects
4. Ask what I'd like to do with the emails (update people data, insert into project notes, file communications, etc.)

Important:
- The output directory is ephemeral — not synced to git or SharePoint
- When referencing email content, read the individual `*_body.txt` files
- Attachments are saved alongside body files in the output directory
