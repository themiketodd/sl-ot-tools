#!/bin/bash
#
# sync.sh — Generic bidirectional sync engine
#
# Reads a sync-map.conf to determine folder mappings between a local
# project directory and a remote directory (e.g., SharePoint/OneDrive).
#
# Usage:
#   sync.sh pull [--dry-run] [-c config]    Remote → Local
#   sync.sh push [--dry-run] [-c config]    Local → Remote
#
# Options:
#   pull          Sync from remote to local
#   push          Sync from local to remote
#   --dry-run     Preview changes without copying
#   -c <file>     Path to sync-map.conf (default: ./sync-map.conf)
#
# Config format: see sync-map.conf for documentation.
#
# Root resolution:
#   LOCAL_ROOT:  If not in conf, auto-resolved from conf file's parent dir
#   REMOTE_ROOT: If not in conf, resolved from .local/user-config.json
#   Env overrides: SL_OT_LOCAL_ROOT, SL_OT_REMOTE_ROOT
#

set -euo pipefail

# --- Defaults ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="./sync-map.conf"
DIRECTION=""
DRY_RUN=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        pull|push)
            DIRECTION="$1"
            shift
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        -c)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: sync.sh <pull|push> [--dry-run] [-c config]"
            echo ""
            echo "  pull          Remote → Local"
            echo "  push          Local → Remote"
            echo "  --dry-run     Preview changes without copying"
            echo "  -c <file>     Path to sync-map.conf"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1"
            echo "Usage: sync.sh <pull|push> [--dry-run] [-c config]"
            exit 1
            ;;
    esac
done

if [[ -z "$DIRECTION" ]]; then
    echo "ERROR: Must specify 'pull' or 'push'"
    echo "Usage: sync.sh <pull|push> [--dry-run] [-c config]"
    exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# --- Parse config file ---
CONF_LOCAL_ROOT=""
CONF_REMOTE_ROOT=""
MAPPINGS=()

while IFS= read -r line; do
    # Skip comments and blank lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue

    # Parse root directives
    if [[ "$line" =~ ^LOCAL_ROOT[[:space:]]*=[[:space:]]*(.*) ]]; then
        CONF_LOCAL_ROOT="${BASH_REMATCH[1]}"
        CONF_LOCAL_ROOT="${CONF_LOCAL_ROOT%"${CONF_LOCAL_ROOT##*[![:space:]]}"}"
        continue
    fi
    if [[ "$line" =~ ^REMOTE_ROOT[[:space:]]*=[[:space:]]*(.*) ]]; then
        CONF_REMOTE_ROOT="${BASH_REMATCH[1]}"
        CONF_REMOTE_ROOT="${CONF_REMOTE_ROOT%"${CONF_REMOTE_ROOT##*[![:space:]]}"}"
        continue
    fi

    # Parse mapping lines: LOCAL | REMOTE | LABEL
    MAPPINGS+=("$line")

done < "$CONFIG_FILE"

# --- Resolve LOCAL_ROOT ---
# Priority: env override → conf file → auto-resolve from conf file's parent
if [[ -n "${SL_OT_LOCAL_ROOT:-}" ]]; then
    LOCAL_ROOT="$SL_OT_LOCAL_ROOT"
elif [[ -n "$CONF_LOCAL_ROOT" ]]; then
    LOCAL_ROOT="$CONF_LOCAL_ROOT"
else
    # Auto-resolve: conf file's parent directory
    CONFIG_DIR="$(cd "$(dirname "$CONFIG_FILE")" && pwd)"
    LOCAL_ROOT="$CONFIG_DIR"
fi

# --- Resolve REMOTE_ROOT ---
# Priority: env override → conf file → .local/user-config.json
if [[ -n "${SL_OT_REMOTE_ROOT:-}" ]]; then
    REMOTE_ROOT="$SL_OT_REMOTE_ROOT"
elif [[ -n "$CONF_REMOTE_ROOT" ]]; then
    REMOTE_ROOT="$CONF_REMOTE_ROOT"
else
    # Auto-resolve from .local/user-config.json
    # Walk up from conf file to find _company/ (repo root is its parent)
    CONFIG_ABS="$(cd "$(dirname "$CONFIG_FILE")" && pwd)"
    REPO_ROOT=""
    CHECK_DIR="$CONFIG_ABS"
    for i in $(seq 1 20); do
        if [[ -d "$CHECK_DIR/_company" ]]; then
            REPO_ROOT="$CHECK_DIR"
            break
        fi
        CHECK_DIR="$(dirname "$CHECK_DIR")"
    done

    if [[ -z "$REPO_ROOT" ]]; then
        echo "ERROR: Cannot auto-resolve REMOTE_ROOT — _company/ not found"
        echo "Set REMOTE_ROOT in sync-map.conf, SL_OT_REMOTE_ROOT env, or .local/user-config.json"
        exit 1
    fi

    USER_CONFIG="$REPO_ROOT/.local/user-config.json"
    if [[ ! -f "$USER_CONFIG" ]]; then
        echo "ERROR: Cannot auto-resolve REMOTE_ROOT — .local/user-config.json not found"
        echo "Run: sl-ot-tools setup"
        exit 1
    fi

    # Detect engagement name from conf file's directory name
    ENGAGEMENT_DIR_NAME="$(basename "$CONFIG_ABS")"
    ONEDRIVE_ROOT=$(python3 -c "
import json, sys
cfg = json.load(open('$USER_CONFIG'))
print(cfg.get('onedrive_root', ''))
" 2>/dev/null)

    ONEDRIVE_MAPPING=$(python3 -c "
import json, sys
cfg = json.load(open('$USER_CONFIG'))
print(cfg.get('onedrive_mappings', {}).get('$ENGAGEMENT_DIR_NAME', ''))
" 2>/dev/null)

    if [[ -z "$ONEDRIVE_ROOT" || -z "$ONEDRIVE_MAPPING" ]]; then
        echo "ERROR: Cannot resolve REMOTE_ROOT from user-config.json"
        echo "  Engagement: $ENGAGEMENT_DIR_NAME"
        echo "  Run: sl-ot-tools setup"
        exit 1
    fi

    REMOTE_ROOT="$ONEDRIVE_ROOT/$ONEDRIVE_MAPPING"
fi

# --- Verify directories exist ---
if [[ ! -d "$LOCAL_ROOT" ]]; then
    echo "ERROR: Local root not found: $LOCAL_ROOT"
    exit 1
fi
if [[ ! -d "$REMOTE_ROOT" ]]; then
    echo "ERROR: Remote root not found: $REMOTE_ROOT"
    echo "Make sure OneDrive is running and the folder is synced."
    exit 1
fi

# --- Setup ---
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Store logs in .local/ if available, otherwise in LOCAL_ROOT
REPO_ROOT_FOR_LOG=""
CHECK_DIR_LOG="$LOCAL_ROOT"
for i in $(seq 1 20); do
    if [[ -d "$CHECK_DIR_LOG/_company" ]]; then
        REPO_ROOT_FOR_LOG="$CHECK_DIR_LOG"
        break
    fi
    CHECK_DIR_LOG="$(dirname "$CHECK_DIR_LOG")"
done

if [[ -n "$REPO_ROOT_FOR_LOG" ]]; then
    LOG_DIR="$REPO_ROOT_FOR_LOG/.local/sync_logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/sync_log_${DIRECTION}_${TIMESTAMP}.txt"
else
    LOG_FILE="${LOCAL_ROOT}/sync_log_${DIRECTION}_${TIMESTAMP}.txt"
fi

# Rsync exclude patterns
EXCLUDES=(
    --exclude '~$*'
    --exclude '*.tmp'
    --exclude '.DS_Store'
    --exclude 'Thumbs.db'
    --exclude 'Desktop.ini'
    --exclude '*Zone.Identifier'
    --exclude '*:Zone.Identifier'
    --exclude '.git'
    --exclude '.gitignore'
    --exclude '.claude'
    --exclude '_tools'
    --exclude '_company'
    --exclude '.local'
    --exclude 'CONTRIBUTING.md'
    --exclude 'sync_log_*.txt'
    --exclude 'sync_from_sharepoint.sh'
    --exclude 'sync_to_sharepoint.sh'
)

log() {
    echo "$1" | tee -a "$LOG_FILE"
}

sync_directory() {
    local src="$1"
    local dst="$2"
    local label="$3"

    if [[ ! -d "$src" ]]; then
        log "  SKIP (source not found): $label"
        return
    fi

    mkdir -p "$dst"
    log ""
    log "--- $label ---"
    log "  FROM: $src"
    log "  TO:   $dst"

    local rsync_mode_opts=()
    if [[ "$DIRECTION" == "pull" ]]; then
        rsync_mode_opts=(--ignore-existing)
    else
        rsync_mode_opts=(--update)
    fi

    rsync -av "${rsync_mode_opts[@]}" "${EXCLUDES[@]}" $DRY_RUN "$src/" "$dst/" 2>&1 | tee -a "$LOG_FILE"
}

sync_file() {
    local src_file="$1"
    local dst_dir="$2"
    local label="$3"

    if [[ ! -f "$src_file" ]]; then
        log "  SKIP (file not found): $label"
        return
    fi

    mkdir -p "$dst_dir"
    log ""
    log "--- $label ---"
    log "  FROM: $src_file"
    log "  TO:   $dst_dir/"

    local rsync_mode_opts=()
    if [[ "$DIRECTION" == "pull" ]]; then
        rsync_mode_opts=(--ignore-existing)
    else
        rsync_mode_opts=(--update)
    fi

    rsync -av "${rsync_mode_opts[@]}" "${EXCLUDES[@]}" $DRY_RUN "$src_file" "$dst_dir/" 2>&1 | tee -a "$LOG_FILE"
}

# --- Header ---
if [[ -n "$DRY_RUN" ]]; then
    echo "=== DRY RUN MODE — no files will be copied ==="
fi

log "=========================================="
if [[ "$DIRECTION" == "pull" ]]; then
    log "PULL: Remote → Local — ${TIMESTAMP}"
else
    log "PUSH: Local → Remote — ${TIMESTAMP}"
fi
log "=========================================="
log "Local root:  $LOCAL_ROOT"
log "Remote root: $REMOTE_ROOT"
log "Config:      $CONFIG_FILE"

# --- Process mappings ---
for mapping in "${MAPPINGS[@]}"; do
    # Parse: LOCAL_PATH | REMOTE_PATH | LABEL
    IFS='|' read -r local_rel remote_rel label <<< "$mapping"

    # Trim whitespace
    local_rel="$(echo "$local_rel" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    remote_rel="$(echo "$remote_rel" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    label="$(echo "$label" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

    # Handle "." as root
    if [[ "$remote_rel" == "." ]]; then
        remote_abs="$REMOTE_ROOT"
    else
        remote_abs="$REMOTE_ROOT/$remote_rel"
    fi

    # Check for direction-restricted mapping (push: or pull: prefix)
    restricted_dir=""
    if [[ "$local_rel" == push:* ]]; then
        restricted_dir="push"
        local_rel="${local_rel#push:}"
    elif [[ "$local_rel" == pull:* ]]; then
        restricted_dir="pull"
        local_rel="${local_rel#pull:}"
    fi

    # Skip if direction doesn't match restriction
    if [[ -n "$restricted_dir" && "$restricted_dir" != "$DIRECTION" ]]; then
        log "  SKIP (${restricted_dir}-only): $label"
        continue
    fi

    # Determine if this is a file or directory mapping
    is_file=false
    if [[ "$local_rel" == file:* ]]; then
        is_file=true
        local_rel="${local_rel#file:}"
    fi

    local_abs="$LOCAL_ROOT/$local_rel"

    # Set source and destination based on direction
    if [[ "$DIRECTION" == "pull" ]]; then
        if [[ "$is_file" == true ]]; then
            # For pull: source is the file in remote, dest is the directory in local
            remote_file="$remote_abs/$(basename "$local_rel")"
            local_dir="$(dirname "$local_abs")"
            sync_file "$remote_file" "$local_dir" "$label"
        else
            sync_directory "$remote_abs" "$local_abs" "$label"
        fi
    else
        if [[ "$is_file" == true ]]; then
            sync_file "$local_abs" "$remote_abs" "$label"
        else
            sync_directory "$local_abs" "$remote_abs" "$label"
        fi
    fi
done

# --- Footer ---
log ""
log "=========================================="
log "Sync complete."
log "=========================================="
log ""
if [[ "$DIRECTION" == "pull" ]]; then
    log "Next steps:"
    log "  git status                    # see new text files"
    log "  git add <files>               # stage text files"
    log "  git commit -m \"sync: ...\"     # commit"
    log "  git push origin main"
else
    log "Files pushed to: $REMOTE_ROOT"
    log "OneDrive will sync them to SharePoint automatically."
fi
log ""
log "Log saved to: $LOG_FILE"
