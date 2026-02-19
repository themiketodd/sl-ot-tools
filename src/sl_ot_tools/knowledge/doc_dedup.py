"""File-path + hash deduplication for document knowledge checkpoints.

Analogous to dedup.py but keyed on file_path|sha256 instead of
subject+date, since documents are identified by their content hash
rather than email metadata.
"""

import json
from datetime import datetime
from pathlib import Path


def make_doc_dedup_key(relative_path: str, sha256: str) -> str:
    """Create a dedup key from file path and content hash.

    Args:
        relative_path: Relative path to the document from repo root.
        sha256: SHA256 hash of the document.

    Returns:
        Dedup key in format "relative_path|sha256".
    """
    return f"{relative_path}|{sha256}"


def load_doc_checkpoint(path: Path) -> dict:
    """Load a document knowledge checkpoint file.

    Returns:
        Dict with 'last_updated' and 'processed' (list of dedup entries).
    """
    if not path.exists():
        return {"last_updated": None, "processed": []}
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_doc_checkpoint(path: Path, checkpoint: dict) -> None:
    """Save a document knowledge checkpoint file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint["last_updated"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)


def get_processed_keys(checkpoint: dict) -> set:
    """Extract the set of dedup keys from a checkpoint."""
    return {entry["key"] for entry in checkpoint.get("processed", [])}


def is_doc_processed(checkpoint: dict, relative_path: str, sha256: str) -> bool:
    """Check if a document has already been processed.

    Args:
        checkpoint: The checkpoint dict.
        relative_path: Relative path to the document.
        sha256: SHA256 hash of the document.

    Returns:
        True if this path+hash combo was already processed.
    """
    key = make_doc_dedup_key(relative_path, sha256)
    return key in get_processed_keys(checkpoint)


def add_to_doc_checkpoint(
    checkpoint: dict, relative_path: str, sha256: str, filename: str
) -> str:
    """Add a document to the checkpoint.

    Args:
        checkpoint: The checkpoint dict to modify in-place.
        relative_path: Relative path to the document.
        sha256: SHA256 hash of the document.
        filename: Original filename for display.

    Returns:
        The dedup key that was added.
    """
    key = make_doc_dedup_key(relative_path, sha256)
    checkpoint.setdefault("processed", []).append(
        {
            "key": key,
            "relative_path": relative_path,
            "sha256": sha256,
            "filename": filename,
        }
    )
    return key
