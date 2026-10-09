"""Format-only edits, designed to avoid changes to meaning and Markdown code."""
from __future__ import annotations
import difflib
from .parser import parse_lines


def safe_fix(text: str) -> str:
    """Trim trailing tabs/spaces only. Preserve fenced/indented code and Markdown hard breaks."""
    original_lines = text.splitlines(keepends=True)
    classified = parse_lines(text)
    output: list[str] = []
    for original, info in zip(original_lines, classified):
        newline = "\r\n" if original.endswith("\r\n") else "\n" if original.endswith("\n") else ""
        content = original[:-len(newline)] if newline else original
        if info.kind in ("code", "frontmatter"):
            output.append(original)
            continue
        trailing_spaces = len(content) - len(content.rstrip(" "))
        if trailing_spaces >= 2 and content.rstrip(" ").strip():
            # Markdown hard line break: use exactly two trailing spaces.
            content = content.rstrip(" \t") + "  "
        else:
            content = content.rstrip(" \t")
        output.append(content + newline)
    return "".join(output)


def unified_diff(original: str, revised: str, fromfile: str = "original", tofile: str = "fixed") -> str:
    return "".join(difflib.unified_diff(original.splitlines(keepends=True), revised.splitlines(keepends=True), fromfile=fromfile, tofile=tofile))
