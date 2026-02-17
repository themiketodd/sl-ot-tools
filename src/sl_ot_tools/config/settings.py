"""
settings.py — User settings loader for ~/.config/sl-ot-tools/.

Provides:
    load_settings()  — load and return parsed TOML settings
    get_setting()    — dot-notation accessor with default
    get_prompt()     — read a prompt snippet from prompts/ dir
    init_settings()  — interactive setup
    main()           — entry point for sl-ot-settings CLI
"""

import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from .write_toml import write_toml

SETTINGS_DIR = Path.home() / ".config" / "sl-ot-tools"
SETTINGS_FILE = SETTINGS_DIR / "settings.toml"
PROMPTS_DIR = SETTINGS_DIR / "prompts"

_DEFAULT_SETTINGS = {
    "general": {
        "timezone": "America/Los_Angeles",
    },
    "email": {
        "powershell_path": "/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe",
        "default_days": 7,
        "default_folders": "Inbox,Archive",
        "skip_inline": False,
        "default_account": "",
    },
    "docgen": {
        "word_template": "",
    },
}


def load_settings() -> dict:
    """Load and return parsed TOML settings. Returns empty dict if missing."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def get_setting(key_path: str, default=None):
    """Dot-notation accessor, e.g. get_setting("general.timezone", "UTC")."""
    settings = load_settings()
    parts = key_path.split(".")
    current = settings
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def get_prompt(name: str) -> str | None:
    """Read prompts/{name}.md if it exists, else None."""
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def init_settings() -> None:
    """Interactive setup: prompt for settings and write settings.toml."""
    print("=== sl-ot-tools Settings ===")
    print(f"Config directory: {SETTINGS_DIR}")
    print()

    # Load existing settings as defaults
    existing = load_settings()

    def _existing(section: str, key: str):
        return existing.get(section, {}).get(key, _DEFAULT_SETTINGS.get(section, {}).get(key))

    # General
    tz_default = _existing("general", "timezone")
    tz = input(f"Timezone [{tz_default}]: ").strip() or tz_default

    # Email
    ps_default = _existing("email", "powershell_path")
    ps_path = input(f"PowerShell path [{ps_default}]: ").strip() or ps_default

    days_default = _existing("email", "default_days")
    days_input = input(f"Default email lookback days [{days_default}]: ").strip()
    days = int(days_input) if days_input else days_default

    folders_default = _existing("email", "default_folders")
    folders = input(f"Default email folders [{folders_default}]: ").strip() or folders_default

    skip_default = _existing("email", "skip_inline")
    skip_display = "yes" if skip_default else "no"
    skip_input = input(f"Skip inline attachments? (yes/no) [{skip_display}]: ").strip().lower()
    if skip_input in ("yes", "y", "true"):
        skip_inline = True
    elif skip_input in ("no", "n", "false"):
        skip_inline = False
    else:
        skip_inline = skip_default

    account_default = _existing("email", "default_account")
    account = input(f"Default Outlook account [{account_default}]: ").strip() or account_default

    # Docgen
    template_default = _existing("docgen", "word_template")
    template = input(f"Word template path (.docx/.dotx) [{template_default}]: ").strip() or template_default

    # Build settings dict
    settings = {
        "general": {
            "timezone": tz,
        },
        "email": {
            "powershell_path": ps_path,
            "default_days": days,
            "default_folders": folders,
            "skip_inline": skip_inline,
            "default_account": account,
        },
        "docgen": {
            "word_template": template,
        },
    }

    # Write
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    write_toml(settings, SETTINGS_FILE)

    print()
    print(f"Saved: {SETTINGS_FILE}")
    print(f"Prompts directory: {PROMPTS_DIR}")
    print()
    print("You can place .md prompt snippets in the prompts/ directory.")
    print("For example, create prompts/email-tone.md to customize email drafting style.")


def main():
    """Entry point for sl-ot-settings CLI command."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Usage: sl-ot-settings")
        print()
        print("Interactive setup for user-specific sl-ot-tools settings.")
        print(f"Config stored at: {SETTINGS_DIR}")
        sys.exit(0)

    init_settings()


if __name__ == "__main__":
    main()
