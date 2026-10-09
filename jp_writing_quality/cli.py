"""CLI: lint, compare, fix. 0=gate pass; 1=gate failure; 2=usage/error."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .analyzer import analyze, compare_preservation, fail_gate, load_rules
from .fixer import safe_fix, unified_diff


def format_report(report: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    m = report["metrics"]
    counts = report["issue_counts"]
    if output_format == "markdown":
        out = [f"# Quality report: {report['file']}", "", f"- 文数: {m['sentences']} / 最長文: {m['longest_sentence_chars']}文字", f"- ERROR: {counts['ERROR']} / WARN: {counts['WARN']} / REVIEW: {counts['REVIEW']}", "", "| 種別 | 箇所 | 内容 |", "| --- | --- | --- |"]
        for f in report["findings"]:
            desc = f["message"].replace("|", "\\|")
            out.append(f"| {f['severity']} {f['rule_id']} | {f['line']}:{f['column']} | {desc} |")
        return "\n".join(out) + "\n"
    out = [f"{report['file']}: 文数={m['sentences']}, 最長文={m['longest_sentence_chars']}文字, ERROR={counts['ERROR']}, WARN={counts['WARN']}, REVIEW={counts['REVIEW']}"]
    for f in report["findings"]:
        out.append(f"{f['line']}:{f['column']} [{f['severity']}] {f['rule_id']}: {f['message']} 例: {f['excerpt'][:70]}")
    return "\n".join(out) + "\n"


def execute(args: argparse.Namespace) -> int:
    rules = load_rules(args.profile, args.rules)
    original = Path(args.input).read_text(encoding="utf-8-sig")
    if args.action == "fix":
        updated = safe_fix(original)
        if args.in_place:
            dest = Path(args.input)
        else:
            if not args.output:
                raise ValueError("fix requires --output or --in-place")
            dest = Path(args.output)
        if dest != Path(args.input) and dest.exists():
            raise ValueError(f"output already exists: {dest} (will not overwrite)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(updated, encoding="utf-8")
        diff = unified_diff(original, updated, args.input, str(dest))
        print(diff if diff else "No safe formatting edits were needed.")
        return 0
    if args.action == "compare":
        revised = Path(args.revised).read_text(encoding="utf-8-sig")
        report = analyze(revised, rules, args.revised)
        report["before_metrics"] = analyze(original, rules, args.input)["metrics"]
        preservation = compare_preservation(original, revised, rules)
        report["findings"].extend(preservation)
        report["findings"].sort(key=lambda f: (f["line"], f["column"], f["rule_id"]))
        report["issue_counts"] = {s: sum(f["severity"] == s for f in report["findings"]) for s in ("ERROR", "WARN", "REVIEW")}
        report["original_file"] = args.input
    else:
        report = analyze(original, rules, args.input)
    rendered = format_report(report, args.format)
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered, encoding="utf-8")
        print(f"Report saved: {dest} (ERROR={report['issue_counts']['ERROR']}, WARN={report['issue_counts']['WARN']}, REVIEW={report['issue_counts']['REVIEW']})")
    else:
        print(rendered, end="")
    return 1 if fail_gate(report, args.fail_on) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jp-writing-lint", description="LLMを使わない日本語文章品質チェッカー")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("lint", "compare", "fix"):
        p = sub.add_parser(action)
        p.add_argument("input", help="入力 Markdown / text (UTF-8)")
        if action == "compare":
            p.add_argument("revised", help="比較する修正版")
        p.add_argument("--profile", choices=["general", "technical"], default="general")
        p.add_argument("--rules", help="上書き用JSONルール")
        p.add_argument("--output", help="レポート出力先、またはfixの保存先")
        if action == "fix":
            p.add_argument("--in-place", action="store_true", help="元ファイルを上書き")
        else:
            p.add_argument("--format", choices=["text", "json", "markdown"], default="text")
            p.add_argument("--fail-on", choices=["none", "error", "warn", "review"], default="error")
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
