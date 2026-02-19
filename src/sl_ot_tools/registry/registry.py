"""Engagement registry: single source of truth for hierarchy, status, governance, and RACI."""

import json
from pathlib import Path
from typing import Optional

GOVERNANCE_TYPES = {
    "steering_committee": "Executive-level decision forum",
    "technical_review": "Architecture and implementation review",
    "executive_sponsor": "Single executive owner",
    "working_group": "Cross-functional operational team",
    "advisory_board": "External advisory and guidance",
}

REGISTRY_FILENAME = "engagement_registry.json"


def load_registry(company_dir: Path) -> Optional[dict]:
    """Load engagement_registry.json from _company/ directory.

    Returns None if the file does not exist.
    """
    path = company_dir / REGISTRY_FILENAME
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_registry(company_dir: Path, data: dict) -> Path:
    """Write engagement_registry.json to _company/ directory.

    Returns the path written.
    """
    path = company_dir / REGISTRY_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def _make_id(name: str) -> str:
    """Replicate the viewer's makeId: lowercase, collapse non-alnum to _, strip edges."""
    import re
    return re.sub(r"(^_|_$)", "", re.sub(r"[^a-z0-9]+", "_", name.lower()))


def build_registry_from_legacy(repo_root: Path) -> dict:
    """Build an engagement_registry.json from legacy org_chart key_programs + engagement configs.

    Reads:
      - _company/org_chart.json → key_programs (array or dict)
      - <engagement>/engagement_config.json → workstreams.*.programs

    Maps key_altera_contacts into RACI responsible field.
    Nests sub_programs as workstreams under their parent engagement.

    Returns the registry dict ready to be saved.
    """
    from ..config.resolver import load_json

    company_dir = repo_root / "_company"
    org_chart_path = company_dir / "org_chart.json"

    # Load org chart for key_programs
    org_data = {}
    if org_chart_path.exists():
        org_data = load_json(org_chart_path)

    # Normalize key_programs to a dict keyed by program key
    programs_by_key = {}
    raw_programs = org_data.get("key_programs", [])
    if isinstance(raw_programs, list):
        for prog in raw_programs:
            if isinstance(prog, dict):
                key = prog.get("key", _make_id(prog.get("name", "")))
                programs_by_key[key] = prog
    elif isinstance(raw_programs, dict):
        for k, v in raw_programs.items():
            if isinstance(v, dict):
                programs_by_key[k] = {**v, "key": k}

    # Build reverse map: program_key -> parent_key (from sub_programs)
    child_to_parent = {}
    for prog_key, prog in programs_by_key.items():
        for sub in prog.get("sub_programs", []):
            sub_key = sub if isinstance(sub, str) else sub.get("key", _make_id(sub.get("name", "")))
            child_to_parent[sub_key] = prog_key

    # Scan engagement configs for workstream -> program mappings
    ws_to_programs = {}  # (eng_key, ws_key) -> [program_keys]
    eng_configs = {}
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
        eng_configs[eng_key] = cfg
        for ws_key, ws_data in cfg.get("workstreams", {}).items():
            if isinstance(ws_data, dict):
                progs = ws_data.get("programs", [])
                if progs:
                    ws_to_programs[(eng_key, ws_key)] = progs

    # Build the registry structure
    engagements = {}

    # Strategy: for each top-level program (not a sub_program), create an engagement entry.
    # Sub-programs become workstreams under that engagement.
    # Also cross-reference ws_to_programs to place programs that are referenced from engagement configs.
    top_level_progs = {k: v for k, v in programs_by_key.items() if k not in child_to_parent}

    for prog_key, prog in top_level_progs.items():
        # Find which engagement references this program
        eng_key_for_prog = None
        for (ek, wk), prog_list in ws_to_programs.items():
            if prog_key in prog_list:
                eng_key_for_prog = ek
                break
            # Also check sub_programs
            for sub in prog.get("sub_programs", []):
                sub_key = sub if isinstance(sub, str) else sub.get("key", "")
                if sub_key in prog_list:
                    eng_key_for_prog = ek
                    break

        # Build RACI from key_altera_contacts
        contacts = prog.get("key_altera_contacts", [])
        raci = {"responsible": contacts, "accountable": [], "consulted": [], "informed": []}

        # Build workstreams from sub_programs
        workstreams = {}
        for sub in prog.get("sub_programs", []):
            if isinstance(sub, str):
                sub_data = programs_by_key.get(sub, {})
                sub_key = sub
            else:
                sub_key = sub.get("key", _make_id(sub.get("name", "")))
                sub_data = programs_by_key.get(sub_key, sub)

            sub_contacts = sub_data.get("key_altera_contacts", [])
            ws_raci = {"responsible": sub_contacts, "accountable": contacts[:1], "consulted": [], "informed": []}

            workstreams[sub_key] = {
                "label": sub_data.get("name", sub_data.get("description", sub_key)),
                "status": sub_data.get("status", "active"),
                "governance": sub_data.get("governance", "working_group"),
                "raci": ws_raci,
            }

        eng_entry = {
            "label": prog.get("name", prog.get("description", prog_key)),
            "status": prog.get("status", "active"),
            "governance": prog.get("governance", "steering_committee"),
            "raci": raci,
        }
        if workstreams:
            eng_entry["workstreams"] = workstreams

        # Use the engagement key from config if found, otherwise use prog_key
        registry_eng_key = eng_key_for_prog or prog_key
        engagements[registry_eng_key] = eng_entry

    registry = {
        "governance_types": dict(GOVERNANCE_TYPES),
        "engagements": engagements,
    }

    return registry


def validate_registry(repo_root: Path) -> dict:
    """Validate registry against org chart and engagement configs.

    Returns dict with:
      - raci_mismatches: list of {engagement, workstream, role, name, reason}
      - orphan_engagements: list of engagement keys in registry with no engagement dir
      - orphan_workstreams: list of (eng_key, ws_key) in engagement configs but not in registry
      - valid: bool
    """
    from ..config.resolver import load_json

    company_dir = repo_root / "_company"
    registry = load_registry(company_dir)
    if registry is None:
        return {
            "raci_mismatches": [],
            "orphan_engagements": [],
            "orphan_workstreams": [],
            "valid": False,
            "error": "No engagement_registry.json found",
        }

    # Load org chart to build person name -> ID map
    org_chart_path = company_dir / "org_chart.json"
    person_ids = set()
    if org_chart_path.exists():
        org_data = load_json(org_chart_path)
        for section in ("leadership", "people", "team"):
            for person in org_data.get(section, []):
                person_ids.add(_make_id(person.get("name", "")))
        # Also include external ecosystem contacts
        _collect_external_ids(org_data.get("external_ecosystem", {}), person_ids)

    # Validate RACI names
    raci_mismatches = []
    for eng_key, eng in registry.get("engagements", {}).items():
        _check_raci(eng.get("raci", {}), eng_key, None, person_ids, raci_mismatches)
        for ws_key, ws in eng.get("workstreams", {}).items():
            _check_raci(ws.get("raci", {}), eng_key, ws_key, person_ids, raci_mismatches)

    # Check orphan engagements (in registry but no engagement dir)
    orphan_engagements = []
    for eng_key in registry.get("engagements", {}):
        eng_dir = repo_root / eng_key
        if not eng_dir.is_dir() or not (eng_dir / "engagement_config.json").exists():
            orphan_engagements.append(eng_key)

    # Check orphan workstreams (in engagement config but not in registry)
    orphan_workstreams = []
    registry_ws_keys = set()
    for eng_key, eng in registry.get("engagements", {}).items():
        for ws_key in eng.get("workstreams", {}):
            registry_ws_keys.add((eng_key, ws_key))

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
        for ws_key in cfg.get("workstreams", {}):
            if (eng_key, ws_key) not in registry_ws_keys:
                orphan_workstreams.append((eng_key, ws_key))

    return {
        "raci_mismatches": raci_mismatches,
        "orphan_engagements": orphan_engagements,
        "orphan_workstreams": orphan_workstreams,
        "valid": len(raci_mismatches) == 0 and len(orphan_engagements) == 0 and len(orphan_workstreams) == 0,
    }


def _collect_external_ids(ecosystem: dict, person_ids: set):
    """Recursively collect person IDs from external_ecosystem."""
    if not isinstance(ecosystem, dict):
        return
    if "key_contacts" in ecosystem:
        for person in ecosystem["key_contacts"]:
            person_ids.add(_make_id(person.get("name", "")))
    else:
        for val in ecosystem.values():
            if isinstance(val, dict):
                _collect_external_ids(val, person_ids)


def _check_raci(raci: dict, eng_key: str, ws_key: Optional[str], person_ids: set, mismatches: list):
    """Check that RACI names resolve to known person IDs."""
    for role in ("responsible", "accountable", "consulted", "informed"):
        for name in raci.get(role, []):
            pid = _make_id(name)
            if pid not in person_ids:
                mismatches.append({
                    "engagement": eng_key,
                    "workstream": ws_key,
                    "role": role,
                    "name": name,
                    "reason": f"Name '{name}' (id: {pid}) not found in org chart",
                })


def get_workstream_contacts(registry: dict, eng_key: str, ws_key: str) -> list:
    """Flatten RACI into a list of contact names for classification.

    Returns all unique names from the workstream's RACI (R, A, C, I),
    with engagement-level RACI as fallback if no workstream RACI.
    """
    eng = registry.get("engagements", {}).get(eng_key, {})
    ws = eng.get("workstreams", {}).get(ws_key, {})

    raci = ws.get("raci") or eng.get("raci", {})
    names = []
    seen = set()
    for role in ("responsible", "accountable", "consulted", "informed"):
        for name in raci.get(role, []):
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names
