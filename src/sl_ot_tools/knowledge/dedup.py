"""Subject+date deduplication for knowledge checkpoints.

This module provides cross-user email deduplication. Different users have
different Outlook EntryIDs for the same email, so we normalize on
subject + date instead.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def normalize_subject(subject: str) -> str:
    """Strip RE:/FW:/FWD: prefixes, lowercase, collapse whitespace."""
    s = subject.strip()
    while True:
        match = re.match(r"^(?:re|fw|fwd)\s*:\s*", s, re.IGNORECASE)
        if not match:
            break
        s = s[match.end() :]
    return re.sub(r"\s+", " ", s.lower()).strip()


def make_dedup_key(subject: str, date_str: str) -> str:
    """Create a dedup key from subject and date.

    Args:
        subject: Email subject line (RE:/FW: prefixes stripped).
        date_str: ISO date string (only first 10 chars = date portion used).

    Returns:
        Dedup key in format "normalized_subject|YYYY-MM-DD".
    """
    return f"{normalize_subject(subject)}|{date_str[:10]}"


def load_checkpoint(path: Path) -> dict:
    """Load a knowledge checkpoint file.

    Returns:
        Dict with 'last_updated' and 'processed' (list of dedup entries).
    """
    if not path.exists():
        return {"last_updated": None, "processed": []}
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_checkpoint(path: Path, checkpoint: dict) -> None:
    """Save a knowledge checkpoint file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint["last_updated"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)


def get_processed_keys(checkpoint: dict) -> set:
    """Extract the set of dedup keys from a checkpoint."""
    return {entry["key"] for entry in checkpoint.get("processed", [])}


def add_to_checkpoint(
    checkpoint: dict, subject: str, date_str: str
) -> str:
    """Add an email to the checkpoint.

    Args:
        checkpoint: The checkpoint dict to modify in-place.
        subject: Original email subject.
        date_str: ISO date string.

    Returns:
        The dedup key that was added.
    """
    key = make_dedup_key(subject, date_str)
    checkpoint.setdefault("processed", []).append(
        {
            "key": key,
            "subject": subject,
            "date": date_str[:10],
        }
    )
    return key


def is_processed(
    checkpoint: dict, subject: str, date_str: str
) -> bool:
    """Check if an email has already been processed.

    Args:
        checkpoint: The checkpoint dict.
        subject: Email subject.
        date_str: ISO date string.

    Returns:
        True if this subject+date combo was already processed.
    """
    key = make_dedup_key(subject, date_str)
    return key in get_processed_keys(checkpoint)


def migrate_from_id_checkpoint(
    old_checkpoint_path: Path,
    emails_index: dict,
    new_checkpoint_path: Optional[Path] = None,
) -> dict:
    """Migrate an old EntryID-based checkpoint to subject+date format.

    Args:
        old_checkpoint_path: Path to old checkpoint with processed_ids.
        emails_index: The emails index.json data (with emails list).
        new_checkpoint_path: Where to save the new checkpoint.

    Returns:
        New checkpoint dict in subject+date format.
    """
    if not old_checkpoint_path.exists():
        return {"last_updated": None, "processed": []}

    with open(old_checkpoint_path, "r", encoding="utf-8-sig") as f:
        old_cp = json.load(f)

    old_ids = set(old_cp.get("processed_ids", []))

    # Build ID → email lookup
    email_by_id = {}
    for email in emails_index.get("emails", []):
        email_by_id[email.get("id", "")] = email

    new_cp = {"last_updated": old_cp.get("last_updated"), "processed": []}
    seen_keys = set()

    for eid in old_ids:
        email = email_by_id.get(eid)
        if email:
            subject = email.get("subject", "")
            date_str = email.get("date", "")
            key = make_dedup_key(subject, date_str)
            if key not in seen_keys:
                seen_keys.add(key)
                new_cp["processed"].append(
                    {"key": key, "subject": subject, "date": date_str[:10]}
                )

    if new_checkpoint_path:
        save_checkpoint(new_checkpoint_path, new_cp)

    return new_cp
