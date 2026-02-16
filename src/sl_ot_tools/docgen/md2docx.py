#!/usr/bin/env python3
"""
md2docx.py — Convert Markdown files to DOCX with proper formatting.

Usage:
    python3 md2docx.py input.md [output.docx]
    sl-ot-md2docx input.md [output.docx]

If output is not specified, uses the input filename with .docx extension.
Sets the document author from git config user.name.
"""

import sys
import os
import subprocess
from pathlib import Path

from .md2docx_renderer import render_markdown_to_docx


def get_git_author() -> str:
    """Get author name from git config, fallback to OS username."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return os.environ.get("USER", "Unknown")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: sl-ot-md2docx input.md [output.docx]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Converts Markdown to DOCX with proper styles, tables,", file=sys.stderr)
        print("lists, code blocks, footnotes, and equations.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Author is set from: git config user.name", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_suffix(".docx")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    md_text = input_path.read_text(encoding="utf-8")
    author = get_git_author()

    render_markdown_to_docx(md_text, str(output_path), author=author)

    print(f"Saved: {output_path}")
    print(f"Author: {author}")


if __name__ == "__main__":
    main()
