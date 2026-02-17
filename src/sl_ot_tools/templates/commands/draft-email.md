Draft an email based on the following request: $ARGUMENTS

Style guidelines: If the file `{{PROMPTS_DIR}}/email-tone.md` exists, read it and apply those tone/style guidelines to the email draft. This allows users to customize their email voice (e.g. formality level, sign-off preferences, phrasing conventions).

Workflow:
1. Based on the request and any relevant context (recent emails, project notes, people data), compose the email:
   - **To**: recipient email address(es)
   - **CC**: if appropriate
   - **Subject**: concise, professional subject line
   - **Body**: well-structured email body

2. Present the full draft to the user for review in a clear format.

3. Ask the user to approve, request edits, or cancel.

4. Once approved, write the body to a temp file and run:
   `sl-ot-draft-email --to "ADDR" --subject "SUBJECT" --body-file /tmp/draft_body.txt`
   Add `--cc "ADDR"` if CC recipients were specified.
   Add `--html` if the body contains HTML formatting.

5. Confirm the draft was created in Outlook's Drafts folder.

Important:
- Always use `--body-file` with a temp file rather than passing the body via `--body` to avoid shell quoting issues
- Use semicolons to separate multiple recipients in --to or --cc
- Look up recipient email addresses from `_company/people/` data if available
- If no recipient email address is specified or can be found, use `placeholder@{{COMPANY_NAME}}.com` as a placeholder so the user can fill it in from Outlook
- Keep the tone professional unless the user specifies otherwise
