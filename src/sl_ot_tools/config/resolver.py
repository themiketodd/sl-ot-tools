"""Config discovery and resolution for sl-ot-tools.

Finds company and engagement directories by walking up the filesystem.
Resolves skip_senders by merging platform → company → engagement configs.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .defaults import PLATFORM_SKIP_SENDERS


def find_company_dir(start_path: Optional[str] = None) -> Optional[Path]:
    """Walk up from start_path to find _company/ directory.

    Args:
        start_path: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to _company/ directory, or None if not found.
    """
    current = Path(start_path or os.getcwd()).resolve()
    for _ in range(20):  # safety limit
        candidate = current / "_company"
        if candidate.is_dir():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def find_repo_root(start_path: Optional[str] = None) -> Optional[Path]:
    """Walk up from start_path to find repo root (parent of _company/).

    Args:
        start_path: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to repo root, or None if not found.
    """
    company_dir = find_company_dir(start_path)
    if company_dir:
        return company_dir.parent
    return None


def find_engagement_dir(start_path: Optional[str] = None) -> Optional[Path]:
    """Detect current engagement directory.

    Walks up from start_path looking for engagement_config.json.

    Args:
        start_path: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to engagement directory, or None if not found.
    """
    current = Path(start_path or os.getcwd()).resolve()
    for _ in range(20):
        if (current / "engagement_config.json").is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def find_local_dir(start_path: Optional[str] = None) -> Optional[Path]:
    """Find .local/ directory in the repo root.

    Args:
        start_path: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to .local/ directory, or None if repo root not found.
    """
    repo_root = find_repo_root(start_path)
    if repo_root:
        return repo_root / ".local"
    return None


def load_json(path: Path) -> dict:
    """Load a JSON file with BOM-safe encoding."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_company_config(start_path: Optional[str] = None) -> dict:
    """Load company_config.json from auto-discovered _company/ directory.

    Returns empty dict if not found.
    """
    company_dir = find_company_dir(start_path)
    if not company_dir:
        return {}
    config_path = company_dir / "company_config.json"
    if not config_path.exists():
        return {}
    return load_json(config_path)


def load_people_config(start_path: Optional[str] = None) -> dict:
    """Load people_config.json from auto-discovered _company/ directory.

    Resolves relative paths against _company/ directory.
    Returns empty dict if not found.
    """
    company_dir = find_company_dir(start_path)
    if not company_dir:
        return {}
    config_path = company_dir / "people_config.json"
    if not config_path.exists():
        return {}

    cfg = load_json(config_path)

    # Resolve relative paths against _company/ directory
    for key in ("org_chart", "checkpoint", "ignore_list"):
        val = cfg.get(key, "")
        if val and not os.path.isabs(val):
            cfg[key] = str((company_dir / val).resolve())

    return cfg


def load_engagement_config(start_path: Optional[str] = None) -> dict:
    """Load engagement_config.json from auto-discovered engagement directory.

    Returns empty dict if not found.
    """
    eng_dir = find_engagement_dir(start_path)
    if not eng_dir:
        return {}
    config_path = eng_dir / "engagement_config.json"
    if not config_path.exists():
        return {}
    return load_json(config_path)


def load_user_config(start_path: Optional[str] = None) -> dict:
    """Load .local/user-config.json from the repo.

    Returns empty dict if not found.
    """
    local_dir = find_local_dir(start_path)
    if not local_dir:
        return {}
    config_path = local_dir / "user-config.json"
    if not config_path.exists():
        return {}
    return load_json(config_path)


def resolve_skip_senders(
    company_config: Optional[dict] = None,
    engagement_config: Optional[dict] = None,
) -> list:
    """Merge skip_senders from platform → company → engagement.

    All three levels are unioned (not overridden). More specific configs
    add to the list, never remove from it.

    Returns:
        Deduplicated list of skip_sender patterns.
    """
    senders = list(PLATFORM_SKIP_SENDERS)
    if company_config:
        senders.extend(company_config.get("skip_senders", []))
    if engagement_config:
        senders.extend(engagement_config.get("skip_senders", []))

    # Deduplicate while preserving order
    seen = set()
    result = []
    for s in senders:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def resolve_onedrive_remote_root(
    engagement_name: str,
    user_config: Optional[dict] = None,
    start_path: Optional[str] = None,
) -> Optional[str]:
    """Resolve the REMOTE_ROOT for an engagement from user config.

    Args:
        engagement_name: The engagement slug (e.g., "enclave").
        user_config: Pre-loaded user config, or None to auto-load.
        start_path: Directory to start searching from.

    Returns:
        Full path to the remote root, or None if not configured.
    """
    if user_config is None:
        user_config = load_user_config(start_path)
    if not user_config:
        return None

    onedrive_root = user_config.get("onedrive_root", "")
    mappings = user_config.get("onedrive_mappings", {})
    relative_path = mappings.get(engagement_name, "")

    if not onedrive_root or not relative_path:
        return None

    return os.path.join(onedrive_root, relative_path)
