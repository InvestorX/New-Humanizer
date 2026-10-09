"""Transparent, configurable, deterministic Japanese writing quality rules."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from typing import Any

from .parser import (
    INLINE_CODE_RE, URL_RE, fenced_blocks, iter_sentences,
    literal_matches, parse_lines, prose_paragraphs,
)

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)*(?:\s?(?:%|％|円|人|件|台|年|月|日|時間|分|秒|ms|s|GB|MB|KB|km|m|cm|mm))?(?![A-Za-z0-9])")
MARKDOWN_LINK_RE = re.compile(r"\]\(([^\s)]+)(?:\s+['\"][^'\"]+['\"])?\)")
CITATION_RE = re.compile(r"\[(?:\^[-\w]+|\d+)\]")
SEVERITIES = {"ERROR": 3, "WARN": 2, "REVIEW": 1}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    line: int
    column: int
    excerpt: str
    message: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_rules(profile: str = "general", override: str | None = None) -> dict[str, Any]:
    presets = {"general", "technical"}
    if profile not in presets:
        raise ValueError(f"unknown profile: {profile}; choose {', '.join(sorted(presets))}")
    path = Path(__file__).with_name("rules") / f"{profile}.json"
    config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if override:
        patch = json.loads(Path(override).read_text(encoding="utf-8"))
        if not isinstance(patch, dict):
            raise ValueError("rules override must be a JSON object")
        config.update(patch)
    for key in ("sentence_warn_chars", "sentence_error_chars", "max_commas", "paragraph_warn_chars"):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if config["sentence_warn_chars"] >= config["sentence_error_chars"]:
        raise ValueError("sentence_warn_chars must be less than sentence_error_chars")
    for key in ("redundant_phrases", "vague_phrases", "lead_headings", "protected_terms"):
        if not isinstance(config.get(key), list) or not all(isinstance(x, str) and x for x in config[key]):
            raise ValueError(f"{key} must be an array of nonempty strings")
    if not isinstance(config.get("term_variants"), list) or not all(isinstance(x, list) and len(x) >= 2 and all(isinstance(y, str) and y for y in x) for x in config["term_variants"]):
        raise ValueError("term_variants must be an array of string arrays")
    return config


def make_finding(rule_id: str, severity: str, line: int, column: int, excerpt: str, message: str, suggestion: str) -> Finding:
    return Finding(rule_id, severity, line, max(column, 1), excerpt[:160], message, suggestion)


def analyze(text: str, rules: dict[str, Any], filename: str = "<stdin>") -> dict[str, Any]:
    lines = parse_lines(text)
    paragraphs = prose_paragraphs(lines)
    sentences = [sentence for paragraph in paragraphs for sentence in iter_sentences(paragraph)]
    headings = [entry for entry in lines if entry.kind == "heading"]
    prose_text = "\n".join(entry.prose for entry in lines if entry.kind == "prose")
    # Descriptive statistics, not a validated readability or cognitive-load score.
    script_characters = [c for c in prose_text if (
        "\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" or
        "\u3400" <= c <= "\u4dbf" or "\u4e00" <= c <= "\u9fff"
    )]
    script_denominator = len(script_characters)
    kanji_count = sum("\u3400" <= c <= "\u4dbf" or "\u4e00" <= c <= "\u9fff" for c in script_characters)
    katakana_count = sum("\u30a0" <= c <= "\u30ff" for c in script_characters)
    findings: list[Finding] = []
    max_length = 0
    for sentence in sentences:
        length = len(sentence.text)
        max_length = max(max_length, length)
        if length > rules["sentence_error_chars"]:
            findings.append(make_finding("SENT001", "ERROR", sentence.line, sentence.column, sentence.text, f"一文が{length}文字（上限{rules['sentence_error_chars']}文字）です。", "主語・結論を明確にし、意味を確認しながら分割してください。"))
        elif length > rules["sentence_warn_chars"]:
            findings.append(make_finding("SENT001", "WARN", sentence.line, sentence.column, sentence.text, f"一文が{length}文字（目安{rules['sentence_warn_chars']}文字超）です。", "情報のまとまりごとに文を分けることを検討してください。"))
        commas = sentence.text.count("、") + sentence.text.count("，")
        if commas > rules["max_commas"]:
            findings.append(make_finding("PUNCT001", "WARN", sentence.line, sentence.column, sentence.text, f"一文に読点が{commas}個あります。", "修飾関係を見直し、文の分割を検討してください。"))
    for paragraph in paragraphs:
        if len(paragraph.text) > rules["paragraph_warn_chars"]:
            findings.append(make_finding("PARA001", "WARN", paragraph.line, paragraph.column, paragraph.text, f"段落が{len(paragraph.text)}文字あります。", "段落の主題ごとに分けてください。"))
    counts = Counter(re.sub(r"\s+", "", p.text) for p in paragraphs if len(p.text) >= 20)
    seen: set[str] = set()
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", "", paragraph.text)
        if len(normalized) < 20 or counts[normalized] < 2 or normalized in seen:
            continue
        seen.add(normalized)
        findings.append(make_finding("DUP001", "WARN", paragraph.line, paragraph.column, paragraph.text, "同じ段落が複数回あります。", "意図的な反復でなければ統合してください。"))
    for entry in lines:
        if entry.kind != "prose":
            continue
        for phrase in rules["redundant_phrases"]:
            for match in re.finditer(re.escape(phrase), entry.prose):
                findings.append(make_finding("STYLE001", "WARN", entry.number, match.start() + 1, phrase, "冗長になりやすい表現です。", "内容を保持した上で短くできるか確認してください（自動置換しません）。"))
        for phrase in rules["vague_phrases"]:
            for match in re.finditer(re.escape(phrase), entry.prose):
                findings.append(make_finding("VAGUE001", "REVIEW", entry.number, match.start() + 1, phrase, "基準が曖昧かもしれません。", "必要なら具体的な基準・条件・担当者を書いてください。"))
    # Domain style variants: flag only when at least two distinct versions occur.
    for group in rules["term_variants"]:
        hits = literal_matches(prose_text, group)
        used = [term for term, count in hits.items() if count]
        if len(used) > 1:
            findings.append(make_finding("TERM001", "WARN", 1, 1, ", ".join(used), "用語の表記が混在しています。", "用語辞書に従ってどちらかに統一してください。"))
    for former, latter in zip(headings, headings[1:]):
        if latter.heading_level > former.heading_level + 1:
            findings.append(make_finding("HEAD001", "WARN", latter.number, 1, latter.original, "見出しレベルが2段階以上飛んでいます。", "見出しの階層を点検してください。"))
    if rules.get("require_lead_heading", False) and len(prose_text) >= rules.get("lead_min_chars", 600):
        first = [h.heading_text for h in headings[:3]]
        if not any(any(keyword in heading for keyword in rules["lead_headings"]) for heading in first):
            findings.append(make_finding("HEAD002", "WARN", 1, 1, "", "冒頭の見出しに概要・結論などが見当たりません。", "読者が最初に判断できる概要または結論を検討してください。"))
    if not prose_text.strip():
        findings.append(make_finding("DOC001", "ERROR", 1, 1, "", "検査対象の本文がありません。", "空文書、またはMarkdownのコードブロックのみではありませんか？"))
    findings.sort(key=lambda f: (f.line, f.column, f.rule_id, f.excerpt))
    issue_counts = {name: sum(f.severity == name for f in findings) for name in SEVERITIES}
    metrics: dict[str, Any] = {
        "source_lines": len(lines), "prose_characters": len(prose_text.strip()),
        "paragraphs": len(paragraphs), "sentences": len(sentences),
        "headings": len(headings), "longest_sentence_chars": max_length,
        "mean_sentence_chars": round(sum(len(s.text) for s in sentences) / len(sentences), 2) if sentences else 0,
        "kanji_fraction_of_japanese_script": round(kanji_count / script_denominator, 4) if script_denominator else 0,
        "katakana_fraction_of_japanese_script": round(katakana_count / script_denominator, 4) if script_denominator else 0,
    }
    return {"schema_version": "1.0", "file": filename, "metrics": metrics, "issue_counts": issue_counts, "findings": [finding.to_dict() for finding in findings]}


def _reference_tokens(text: str, rules: dict[str, Any]) -> dict[str, Counter[str]]:
    """Exact-match guards. Not a semantic-equivalence checker."""
    markdown_link_spans = [m.span() for m in MARKDOWN_LINK_RE.finditer(text)]
    bare_urls = [
        m.group().rstrip("、。,.!?:;)]")
        for m in URL_RE.finditer(text)
        if not any(a <= m.start() < b for a, b in markdown_link_spans)
    ]
    return {
        "numbers_and_units": Counter(NUMBER_RE.findall(text)),
        "urls": Counter(bare_urls),
        "markdown_link_destinations": Counter(MARKDOWN_LINK_RE.findall(text)),
        "citation_markers": Counter(CITATION_RE.findall(text)),
        "inline_code": Counter(m.group() for m in INLINE_CODE_RE.finditer(text)),
        "protected_terms": Counter({term: text.count(term) for term in rules["protected_terms"] if text.count(term)}),
    }


def compare_preservation(original: str, revised: str, rules: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[Finding] = []
    left, right = _reference_tokens(original, rules), _reference_tokens(revised, rules)
    for label in left:
        lost = left[label] - right[label]
        added = right[label] - left[label]
        if lost or added:
            details = f"削除/変更: {dict(lost)}、追加/変更: {dict(added)}"
            findings.append(make_finding("PRESERVE001", "ERROR", 1, 1, label, f"保護対象の差分を検出（{label}）。{details}", "原文との照合と人間による承認が必要です。"))
    if fenced_blocks(original) != fenced_blocks(revised):
        findings.append(make_finding("PRESERVE002", "ERROR", 1, 1, "fenced_code", "コードブロックの内容が変化しました。", "コードの修正が意図的かレビューしてください。"))
    return [f.to_dict() for f in findings]


def fail_gate(report: dict[str, Any], threshold: str) -> bool:
    levels = {"none": 99, "error": 3, "warn": 2, "review": 1}
    return any(SEVERITIES[item["severity"]] >= levels[threshold] for item in report["findings"])
