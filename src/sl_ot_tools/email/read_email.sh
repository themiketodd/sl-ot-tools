#!/bin/bash
#
# read_email.sh — Read emails from Outlook via MAPI COM
#
# Usage:
#   read_email.sh [--days N] [--folders "Inbox,Archive"] [--skip-inline] [--account NAME]
#
# Output: creates .local/email_output/<timestamp>/ with:
#   - index.json (email metadata and summary)
#   - *_body.txt (plain text bodies)
#   - *_body.html (HTML bodies where available)
#   - *_att_* (attachments)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POWERSHELL="/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe"
PS_SCRIPT="$SCRIPT_DIR/read_email.ps1"

# --- Defaults ---
DAYS=7
FOLDERS="Inbox,Archive"
SKIP_INLINE=""
ACCOUNT=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --days)
            DAYS="$2"
            shift 2
            ;;
        --folders)
            FOLDERS="$2"
            shift 2
            ;;
        --skip-inline)
            SKIP_INLINE="-SkipInline"
            shift
            ;;
        --account)
            ACCOUNT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: read_email.sh [--days N] [--folders \"Inbox,Archive\"] [--skip-inline] [--account NAME]"
            echo ""
            echo "  --days N          Look back N days (default: 7)"
            echo "  --folders LIST    Comma-separated folder names (default: Inbox,Archive)"
            echo "  --skip-inline     Skip inline image attachments"
            echo "  --account NAME    Outlook account name (default: primary)"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1"
            exit 1
            ;;
    esac
done

# --- Verify PowerShell ---
if [[ ! -f "$POWERSHELL" ]]; then
    echo "ERROR: PowerShell not found at $POWERSHELL"
    exit 1
fi

# --- Find repo root (walk up to find _company/) ---
REPO_ROOT=""
CHECK_DIR="$(pwd)"
for i in $(seq 1 20); do
    if [[ -d "$CHECK_DIR/_company" ]]; then
        REPO_ROOT="$CHECK_DIR"
        break
    fi
    CHECK_DIR="$(dirname "$CHECK_DIR")"
done

# --- Create output directory ---
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if [[ -n "$REPO_ROOT" ]]; then
    OUTPUT_BASE="$REPO_ROOT/.local/email_output"
else
    OUTPUT_BASE="$SCRIPT_DIR/output"
fi

OUTPUT_DIR="$OUTPUT_BASE/$TIMESTAMP"
mkdir -p "$OUTPUT_DIR"

# PowerShell needs a Windows path. Since our output dir is under the WSL
# filesystem, we use a Windows temp directory and copy results back.
WIN_TEMP=$("$POWERSHELL" -NoProfile -Command '[System.IO.Path]::GetTempPath()' 2>/dev/null | tr -d '\r\n')
WIN_OUTPUT_DIR="${WIN_TEMP}email_export_${TIMESTAMP}"

echo "=== Email Reader ==="
echo "  Days:    $DAYS"
echo "  Folders: $FOLDERS"
echo "  Output:  $OUTPUT_DIR"
echo ""

# --- Convert PS script path to Windows ---
PS_SCRIPT_WIN=$(wslpath -w "$PS_SCRIPT")

# --- Build PowerShell arguments ---
PS_ARGS="-NoProfile -ExecutionPolicy Bypass -File \"$PS_SCRIPT_WIN\" -Days $DAYS -OutputDir \"$WIN_OUTPUT_DIR\" -Folders \"$FOLDERS\""
if [[ -n "$SKIP_INLINE" ]]; then
    PS_ARGS="$PS_ARGS -SkipInline"
fi
if [[ -n "$ACCOUNT" ]]; then
    PS_ARGS="$PS_ARGS -Account \"$ACCOUNT\""
fi

# --- Run PowerShell ---
"$POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$PS_SCRIPT_WIN" \
    -Days "$DAYS" \
    -OutputDir "$WIN_OUTPUT_DIR" \
    -Folders "$FOLDERS" \
    $SKIP_INLINE \
    ${ACCOUNT:+-Account "$ACCOUNT"} \
    2>&1

PS_EXIT=$?

# --- Copy results back to WSL ---
# Convert Windows temp path to WSL mount path
WIN_OUTPUT_WSL=$(wslpath -u "$WIN_OUTPUT_DIR" 2>/dev/null || echo "")

if [[ -n "$WIN_OUTPUT_WSL" && -d "$WIN_OUTPUT_WSL" ]]; then
    cp -r "$WIN_OUTPUT_WSL"/* "$OUTPUT_DIR/" 2>/dev/null || true
    # Clean up Windows temp
    rm -rf "$WIN_OUTPUT_WSL" 2>/dev/null || true
else
    echo "WARNING: Could not copy results from Windows temp directory"
    echo "  Expected: $WIN_OUTPUT_DIR"
fi

# --- Verify output ---
if [[ -f "$OUTPUT_DIR/index.json" ]]; then
    EMAIL_COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT_DIR/index.json', encoding='utf-8-sig')); print(d['stats']['total_emails'])" 2>/dev/null || echo "?")
    echo ""
    echo "=== Done ==="
    echo "  Emails exported: $EMAIL_COUNT"
    echo "  Output: $OUTPUT_DIR"
    echo "  Index:  $OUTPUT_DIR/index.json"
else
    echo ""
    echo "WARNING: index.json not found in output directory"
    echo "  PowerShell exit code: $PS_EXIT"
    echo "  Check $OUTPUT_DIR/_errors.log for details"
fi

# --- Cleanup old output directories (keep last 3) ---
if [[ -d "$OUTPUT_BASE" ]]; then
    ls -dt "$OUTPUT_BASE"/*/ 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null || true
fi

# --- Return the output path (for programmatic use) ---
echo "$OUTPUT_DIR"
