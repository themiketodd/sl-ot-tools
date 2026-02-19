"""File indexer for engagement documents and email attachments.

Scans engagement directories and email output for office documents,
builds a unified file_index.json with smart dedup across sources.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config.resolver import load_json

# File types we index
INDEXED_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".pdf"}


def _sha256(path: Path) -> str:
    """Compute sha256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_entry(path: Path, repo_root: Path, **extra) -> dict:
    """Build a file index entry for a single file."""
    rel = path.relative_to(repo_root)
    stat = path.stat()
    entry = {
        "filename": path.name,
        "relative_path": str(rel),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "size": stat.st_size,
        "file_type": path.suffix.lstrip(".").lower(),
        "sha256": _sha256(path),
        "is_primary": True,
    }
    entry.update(extra)
    return entry


def scan_engagement_files(repo_root: Path) -> list[dict]:
    """Walk each engagement dir for office documents.

    Classifies each file to engagement + workstream by matching its
    directory against engagement_config.json workstream output_dir values.
    """
    entries = []

    for eng_dir in sorted(repo_root.iterdir()):
        if not eng_dir.is_dir():
            continue
        cfg_path = eng_dir / "engagement_config.json"
        if not cfg_path.exists():
            continue

        try:
            cfg = load_json(cfg_path)
        except Exception:
            continue

        eng_key = cfg.get("engagement", eng_dir.name)

        # Build output_dir -> workstream_key map
        ws_map = {}
        for ws_key, ws_data in cfg.get("workstreams", {}).items():
            if isinstance(ws_data, dict):
                output_dir = ws_data.get("output_dir", ws_key)
                ws_map[output_dir] = ws_key

        # Walk for office files
        for path in eng_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in INDEXED_EXTENSIONS:
                continue
            # Skip temp/lock files
            if path.name.startswith("~$"):
                continue

            # Classify to workstream
            rel_to_eng = path.relative_to(eng_dir)
            parts = rel_to_eng.parts
            workstream = None
            if parts:
                # Check if first directory component matches an output_dir
                for od, ws_key in ws_map.items():
                    if parts[0] == od or str(rel_to_eng).startswith(od + "/"):
                        workstream = ws_key
                        break

            entry = _file_entry(
                path, repo_root,
                engagement=eng_key,
                workstream=workstream or "unclassified",
                source="synced",
            )
            entries.append(entry)

    return entries


def scan_email_attachments(repo_root: Path, days_back: int = 7) -> list[dict]:
    """Walk .local/email_output/*/ for attachment files.

    Cross-references index.json for email metadata.

    Args:
        repo_root: Path to repo root.
        days_back: Only look at emails from this many days ago.
    """
    entries = []
    email_output = repo_root / ".local" / "email_output"
    if not email_output.exists():
        return entries

    cutoff = datetime.now().timestamp() - (days_back * 86400)

    for run_dir in sorted(email_output.iterdir()):
        if not run_dir.is_dir():
            continue
        index_path = run_dir / "index.json"
        if not index_path.exists():
            continue

        try:
            index = load_json(index_path)
        except Exception:
            continue

        for email in index.get("emails", []):
            # Check date cutoff
            email_date = email.get("date", "")
            if email_date:
                try:
                    from datetime import datetime as dt
                    parsed = dt.fromisoformat(email_date.replace("Z", "+00:00"))
                    if parsed.timestamp() < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            attachments = email.get("attachments", [])
            if not attachments:
                continue

            for att in attachments:
                att_name = att if isinstance(att, str) else att.get("filename", "")
                if not att_name:
                    continue

                # Look for the attachment file in the run directory
                att_path = run_dir / att_name
                if not att_path.is_file():
                    continue
                if att_path.suffix.lower() not in INDEXED_EXTENSIONS:
                    continue

                entry = _file_entry(
                    att_path, repo_root,
                    source="email_attachment",
                    email_id=email.get("id", ""),
                    email_subject=email.get("subject", ""),
                    original_name=att_name,
                    engagement=None,
                    workstream=None,
                )
                entries.append(entry)

    return entries


def _dedup_entries(entries: list[dict]) -> list[dict]:
    """Smart dedup: group by sha256, keep newest as primary.

    For exact hash matches across sources, the newest by modified timestamp
    wins as primary. Others are marked as duplicates.
    """
    by_hash: dict[str, list[dict]] = {}
    for entry in entries:
        h = entry["sha256"]
        by_hash.setdefault(h, []).append(entry)

    result = []
    for h, group in by_hash.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        # Sort by modified desc — newest first
        group.sort(key=lambda e: e["modified"], reverse=True)
        primary = group[0]
        primary["is_primary"] = True
        result.append(primary)

        for dup in group[1:]:
            dup["is_primary"] = False
            dup["duplicate_of"] = primary["relative_path"]
            result.append(dup)

    return result


def build_file_index(repo_root: Path, days_back: int = 7) -> dict:
    """Build unified file index from engagement dirs and email attachments.

    Args:
        repo_root: Path to the repo root.
        days_back: How far back to look for email attachments.

    Returns:
        File index dict with 'files' list and metadata.
    """
    synced = scan_engagement_files(repo_root)
    attachments = scan_email_attachments(repo_root, days_back=days_back)

    all_entries = synced + attachments
    deduped = _dedup_entries(all_entries)

    # Sort by engagement, then relative path
    deduped.sort(key=lambda e: (e.get("engagement") or "zzz", e["relative_path"]))

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_files": len(deduped),
        "primary_files": sum(1 for e in deduped if e["is_primary"]),
        "duplicates": sum(1 for e in deduped if not e["is_primary"]),
        "files": deduped,
    }


def load_file_index(company_dir: Path) -> Optional[dict]:
    """Load existing file_index.json if it exists."""
    path = company_dir / "file_index.json"
    if path.exists():
        return load_json(path)
    return None


def save_file_index(company_dir: Path, index: dict) -> Path:
    """Write file_index.json to _company/."""
    path = company_dir / "file_index.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path
