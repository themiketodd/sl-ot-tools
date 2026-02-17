Pull the latest files from SharePoint into the local repo.

{{ENGAGEMENT_RESOLUTION}}

1. Run: `<engagement>/sync_from_sharepoint.sh --dry-run`
2. Show me a summary of what would be synced (new files, updated folders)
3. Ask if I want to proceed with the actual sync
4. If yes, run: `<engagement>/sync_from_sharepoint.sh`
5. Run `git status` to show any new text files that should be committed
6. Ask if I want to commit the new text files
