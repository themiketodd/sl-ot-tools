"""Orchestrates document text extraction into markdown summaries.

Reads file_index.json, extracts text from approved primary files,
writes summaries with YAML metadata headers to workstream directories.
Uses sha256-based caching to skip unchanged files.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config.resolver import load_json
from .extractor import extract_text


def _load_triage(company_dir: Path) -> dict:
    """Load doc_triage.json if it exists."""
    path = company_dir / "doc_triage.json"
    if path.exists():
        return load_json(path)
    return {"approved": [], "skipped": [], "skip_patterns": [], "last_updated": None}


def _matches_skip_pattern(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any skip pattern (glob-style)."""
    import fnmatch
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def _summary_path_for(entry: dict, repo_root: Path, engagement_configs: dict) -> Path:
    """Resolve the output path for a summary file.

    Returns: <engagement>/<workstream_output_dir>/_summaries/<stem>.md
    """
    eng = entry.get("engagement")
    ws = entry.get("workstream")

    if eng and ws and ws != "unclassified":
        # Look up the output_dir from engagement config
        cfg = engagement_configs.get(eng, {})
        ws_data = cfg.get("workstreams", {}).get(ws, {})
        output_dir = ws_data.get("output_dir", ws) if isinstance(ws_data, dict) else ws
        base = repo_root / eng / output_dir / "_summaries"
    elif eng:
        base = repo_root / eng / "_summaries"
    else:
        # Unclassified email attachments
        base = repo_root / "_company" / "_summaries" / "unclassified"

    stem = Path(entry["filename"]).stem
    return base / f"{stem}.md"


def _read_existing_hash(summary_path: Path) -> Optional[str]:
    """Read the sha256 from an existing summary's YAML header."""
    if not summary_path.exists():
        return None
    try:
        text = summary_path.read_text(encoding="utf-8")
        match = re.search(r"^sha256:\s*(\S+)", text, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _load_engagement_configs(repo_root: Path) -> dict:
    """Load all engagement_config.json files keyed by engagement name."""
    configs = {}
    for p in repo_root.iterdir():
        if p.is_dir() and (p / "engagement_config.json").exists():
            try:
                configs[p.name] = load_json(p / "engagement_config.json")
            except Exception:
                pass
    return configs


def summarize_files(repo_root: Path, force: bool = False) -> dict:
    """Extract text from all approved primary files in the file index.

    Args:
        repo_root: Path to repo root.
        force: If True, re-extract even if sha256 matches.

    Returns:
        Dict with counts: extracted, skipped, errors.
    """
    company_dir = repo_root / "_company"
    index_path = company_dir / "file_index.json"

    if not index_path.exists():
        return {"error": "file_index.json not found. Run 'sl-ot-tools index-files' first."}

    file_index = load_json(index_path)
    triage = _load_triage(company_dir)
    engagement_configs = _load_engagement_configs(repo_root)

    approved = set(triage.get("approved", []))
    skip_patterns = triage.get("skip_patterns", [])

    extracted = 0
    skipped = 0
    errors = []

    for entry in file_index.get("files", []):
        # Only process primary files
        if not entry.get("is_primary", True):
            skipped += 1
            continue

        rel_path = entry["relative_path"]

        # Check triage state: must be approved (if triage exists)
        if approved and rel_path not in approved:
            skipped += 1
            continue

        # Check skip patterns
        if _matches_skip_pattern(rel_path, skip_patterns):
            skipped += 1
            continue

        # Resolve source file
        source_path = repo_root / rel_path
        if not source_path.exists():
            errors.append(f"File not found: {rel_path}")
            continue

        # Resolve output path
        summary_path = _summary_path_for(entry, repo_root, engagement_configs)

        # Hash-based caching
        if not force:
            existing_hash = _read_existing_hash(summary_path)
            if existing_hash == entry["sha256"]:
                skipped += 1
                continue

        # Extract text
        try:
            text = extract_text(source_path)
        except Exception as e:
            errors.append(f"Extraction failed for {rel_path}: {e}")
            continue

        # Build summary with YAML header
        header = (
            f"---\n"
            f"source_file: {rel_path}\n"
            f"file_type: {entry['file_type']}\n"
            f"sha256: {entry['sha256']}\n"
            f"extraction_date: {datetime.now().isoformat(timespec='seconds')}\n"
            f"source: {entry.get('source', 'synced')}\n"
            f"---\n\n"
        )
        content = header + text

        # Write summary
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(content, encoding="utf-8")
        extracted += 1

    return {
        "extracted": extracted,
        "skipped": skipped,
        "errors": errors,
    }
