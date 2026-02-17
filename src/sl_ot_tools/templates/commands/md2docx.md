Convert a markdown file to a Word document (.docx).

Arguments: $ARGUMENTS should be the path to the .md file, optionally followed by the output .docx path.

{{ENGAGEMENT_RESOLUTION}}

1. Parse the arguments to get input path and optional output path
2. If no output path is given, use the same filename with .docx extension
3. Run: `sl-ot-md2docx <input> <output>`
4. Confirm the output file was created and report the author metadata set
5. Ask if I want to push it to SharePoint via `<engagement>/sync_to_sharepoint.sh`

Supported markdown features: headings, bold/italic, tables, bullet/numbered lists,
code blocks, blockquotes, footnotes, LaTeX math, horizontal rules, and links.
