#!/bin/bash
#
# draft_email.sh — Create a draft email in Outlook via MAPI COM
#
# Usage:
#   draft_email.sh --to "user@example.com" --subject "Hello" --body "Body text"
#   draft_email.sh --to "user@example.com" --subject "Hello" --body-file /path/to/body.txt
#   draft_email.sh --to "user@example.com" --cc "other@example.com" --subject "Hello" --body "Body" --html
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PS_SCRIPT="$SCRIPT_DIR/draft_email.ps1"

# Read settings from ~/.config/sl-ot-tools/settings.toml (with hardcoded fallbacks)
POWERSHELL=$(python3 -c "
from sl_ot_tools.config.settings import get_setting
print(get_setting('email.powershell_path', '/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe'))
" 2>/dev/null || echo "/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe")

TIMEZONE=$(python3 -c "
from sl_ot_tools.config.settings import get_setting
print(get_setting('general.timezone', ''))
" 2>/dev/null || echo "")

# --- Defaults ---
TO=""
CC=""
SUBJECT=""
BODY=""
BODY_FILE=""
BODY_FORMAT="Plain"
ACCOUNT=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --to)
            TO="$2"
            shift 2
            ;;
        --cc)
            CC="$2"
            shift 2
            ;;
        --subject)
            SUBJECT="$2"
            shift 2
            ;;
        --body)
            BODY="$2"
            shift 2
            ;;
        --body-file)
            BODY_FILE="$2"
            shift 2
            ;;
        --html)
            BODY_FORMAT="HTML"
            shift
            ;;
        --account)
            ACCOUNT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: draft_email.sh --to ADDR --subject SUBJ [--body TEXT | --body-file PATH] [OPTIONS]"
            echo ""
            echo "  --to ADDR         Recipient email addresses (semicolon-separated)"
            echo "  --cc ADDR         CC recipients (optional, semicolon-separated)"
            echo "  --subject SUBJ    Email subject line"
            echo "  --body TEXT       Email body text"
            echo "  --body-file PATH  Read email body from file (preferred for long bodies)"
            echo "  --html            Send as HTML format (default: plain text)"
            echo "  --account NAME    Outlook account name (default: primary)"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1"
            exit 1
            ;;
    esac
done

# --- Validate required fields ---
if [[ -z "$TO" ]]; then
    echo "ERROR: --to is required"
    exit 1
fi
if [[ -z "$SUBJECT" ]]; then
    echo "ERROR: --subject is required"
    exit 1
fi
if [[ -z "$BODY" && -z "$BODY_FILE" ]]; then
    echo "ERROR: --body or --body-file is required"
    exit 1
fi

# --- Verify PowerShell ---
if [[ ! -f "$POWERSHELL" ]]; then
    echo "ERROR: PowerShell not found at $POWERSHELL"
    exit 1
fi

# --- Handle body file ---
# If --body was given (not --body-file), write it to a temp file to avoid
# command-line length limits and quoting issues with multi-line content.
CLEANUP_BODY_FILE=""
if [[ -n "$BODY" && -z "$BODY_FILE" ]]; then
    BODY_FILE=$(mktemp /tmp/draft_body_XXXXXX.txt)
    CLEANUP_BODY_FILE="$BODY_FILE"
    printf '%s' "$BODY" > "$BODY_FILE"
fi

# Convert body file path to Windows path
BODY_FILE_WIN=$(wslpath -w "$BODY_FILE")

# --- Convert PS script path to Windows ---
PS_SCRIPT_WIN=$(wslpath -w "$PS_SCRIPT")

# --- Run PowerShell ---
"$POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$PS_SCRIPT_WIN" \
    -To "$TO" \
    ${CC:+-Cc "$CC"} \
    -Subject "$SUBJECT" \
    -BodyFile "$BODY_FILE_WIN" \
    -BodyFormat "$BODY_FORMAT" \
    ${ACCOUNT:+-Account "$ACCOUNT"} \
    ${TIMEZONE:+-Timezone "$TIMEZONE"} \
    2>&1

PS_EXIT=$?

# --- Cleanup temp body file ---
if [[ -n "$CLEANUP_BODY_FILE" ]]; then
    rm -f "$CLEANUP_BODY_FILE" 2>/dev/null || true
fi

exit $PS_EXIT
