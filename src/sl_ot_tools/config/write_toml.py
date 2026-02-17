"""
write_toml.py — Minimal TOML writer for flat-section config files.

Handles the simple structure used by settings.toml: sections with
string, boolean, and integer values. No nested tables or arrays of tables.
"""

from pathlib import Path


def write_toml(data: dict, path: Path) -> None:
    """Serialize a flat-section dict to a TOML file.

    Expected structure: {"section": {"key": value, ...}, ...}
    Values may be str, bool, int, or float.
    """
    lines = []
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, val in values.items():
            lines.append(f"{key} = {_format_value(val)}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_value(val) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(val)
    # Default: quote as string
    escaped = str(val).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
