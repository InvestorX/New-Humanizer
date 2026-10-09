"""Conservative Markdown/text extraction with source locations."""
from __future__ import annotations

from dataclasses import dataclass
import re

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")
LINK_TARGET_RE = re.compile(r"\]\((?:[^()]|\([^()]*\))*\)")
URL_RE = re.compile(r"https?://[^\s<>]+")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
BULLET_RE = re.compile(r"^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)")
HORIZONTAL_RE = re.compile(r"^ {0,3}(?:[-*_]\s*){3,}$")
SENTENCE_END = set("。！？!?")


@dataclass(frozen=True)
class SourceLine:
    number: int
    original: str
    prose: str
    kind: str  # prose, heading, blank, code, frontmatter, table, rule
    heading_level: int = 0
    heading_text: str = ""


@dataclass(frozen=True)
class LocatedSpan:
    text: str
    line: int
    column: int


def mask_match(match: re.Match[str]) -> str:
    return " " * len(match.group())


def mask_inline_markup(value: str) -> str:
    """Mask inline code/URLs while retaining text offsets and human-visible link captions."""
    value = INLINE_CODE_RE.sub(mask_match, value)
    value = LINK_TARGET_RE.sub(mask_match, value)
    value = URL_RE.sub(mask_match, value)
    return value


def parse_lines(text: str) -> list[SourceLine]:
    lines = text.splitlines()
    result: list[SourceLine] = []
    fence_mark = ""
    fence_len = 0
    yaml = bool(lines and lines[0].strip() == "---")
    for index, original in enumerate(lines, start=1):
        stripped = original.strip()
        if yaml:
            result.append(SourceLine(index, original, "", "frontmatter"))
            if index > 1 and stripped in ("---", "..."):
                yaml = False
            continue
        marker = FENCE_RE.match(original)
        if fence_mark:
            result.append(SourceLine(index, original, "", "code"))
            if marker and marker.group(1)[0] == fence_mark and len(marker.group(1)) >= fence_len and not marker.group(2).strip():
                fence_mark = ""
                fence_len = 0
            continue
        if marker:
            fence_mark = marker.group(1)[0]
            fence_len = len(marker.group(1))
            result.append(SourceLine(index, original, "", "code"))
            continue
        if not stripped:
            result.append(SourceLine(index, original, "", "blank"))
            continue
        if original.startswith("    ") or original.startswith("\t"):
            result.append(SourceLine(index, original, "", "code"))
            continue
        h = HEADING_RE.match(original)
        if h:
            result.append(SourceLine(index, original, "", "heading", len(h.group(1)), h.group(2).strip()))
            continue
        if HORIZONTAL_RE.match(original):
            result.append(SourceLine(index, original, "", "rule"))
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            result.append(SourceLine(index, original, "", "table"))
            continue
        result.append(SourceLine(index, original, mask_inline_markup(original), "prose"))
    return result


def prose_paragraphs(lines: list[SourceLine]) -> list[LocatedSpan]:
    """Join prose lines until a blank, heading, or list-item boundary."""
    chunks: list[LocatedSpan] = []
    parts: list[str] = []
    start_line = 1
    start_col = 1

    def flush() -> None:
        if parts:
            chunks.append(LocatedSpan(" ".join(parts), start_line, start_col))
            parts.clear()

    for entry in lines:
        if entry.kind != "prose":
            flush()
            continue
        content = entry.prose
        bullet = BULLET_RE.match(content)
        if bullet:
            flush()
            content = content[bullet.end():]
            col = bullet.end() + 1
        else:
            col = len(content) - len(content.lstrip()) + 1
            content = content.strip()
        if not content.strip():
            flush()
            continue
        if not parts:
            start_line, start_col = entry.number, col
        parts.append(content.strip())
    flush()
    return chunks


def iter_sentences(paragraph: LocatedSpan) -> list[LocatedSpan]:
    """Sentences within a paragraph; a paragraph may span several source lines."""
    text = paragraph.text
    result: list[LocatedSpan] = []
    start = 0
    for pos, char in enumerate(text):
        if char in SENTENCE_END and (pos + 1 == len(text) or text[pos + 1] not in SENTENCE_END):
            part = text[start:pos + 1].strip()
            if part:
                result.append(LocatedSpan(part, paragraph.line, paragraph.column + start))
            start = pos + 1
    part = text[start:].strip()
    if part:
        result.append(LocatedSpan(part, paragraph.line, paragraph.column + start))
    return result


def literal_matches(text: str, variants: list[str]) -> dict[str, int]:
    """Count phrases without double-counting shorter overlapping variants."""
    hits: dict[str, int] = {v: 0 for v in variants}
    occupied = [False] * len(text)
    for term in sorted(variants, key=lambda x: (-len(x), x)):
        for match in re.finditer(re.escape(term), text):
            if not any(occupied[match.start():match.end()]):
                hits[term] += 1
                for pos in range(match.start(), match.end()):
                    occupied[pos] = True
    return hits


def fenced_blocks(text: str) -> list[str]:
    lines = parse_lines(text)
    blocks: list[str] = []
    current: list[str] = []
    for entry in lines:
        if entry.kind == "code":
            current.append(entry.original)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks
