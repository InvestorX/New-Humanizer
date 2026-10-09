import json
from pathlib import Path
import tempfile
import unittest

from new_humanizer.analyzer import analyze, compare_preservation, fail_gate, load_rules
from new_humanizer.cli import main
from new_humanizer.fixer import safe_fix
from new_humanizer.parser import parse_lines, prose_paragraphs


class QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()

    def test_long_sentence_causes_error(self):
        report = analyze("あ" * 131 + "。", self.rules)
        self.assertIn("SENT001", [f["rule_id"] for f in report["findings"]])
        self.assertTrue(fail_gate(report, "error"))

    def test_short_clean_sentence_passes(self):
        report = analyze("# 概要\n\nシステムは正常に動作します。", self.rules)
        self.assertEqual(report["issue_counts"]["ERROR"], 0)
        self.assertFalse(fail_gate(report, "warn"))

    def test_code_and_inline_code_are_ignored_for_sentence_rule(self):
        long = "あ" * 200
        text = f"# 見出し\n\n`{long}` は説明対象です。\n\n```python\n{long}。\n```\n"
        report = analyze(text, self.rules)
        self.assertFalse(any(f["rule_id"] == "SENT001" for f in report["findings"]))

    def test_multiline_paragraph_is_joined(self):
        text = "あ" * 45 + "\n" + "あ" * 45 + "。"
        report = analyze(text, self.rules)
        self.assertEqual(report["metrics"]["sentences"], 1)
        self.assertTrue(any(f["rule_id"] == "SENT001" for f in report["findings"]))

    def test_duplicate_paragraph_is_flagged(self):
        para = "同じ説明を繰り返しているため統合できるはずです。"
        report = analyze(para + "\n\n" + para, self.rules)
        self.assertTrue(any(f["rule_id"] == "DUP001" for f in report["findings"]))

    def test_term_variants_are_detected_without_substring_false_positives(self):
        report = analyze("ユーザーとサーバーを管理する。", self.rules)
        self.assertFalse(any(f["rule_id"] == "TERM001" for f in report["findings"]))
        report = analyze("ユーザとユーザーを管理する。", self.rules)
        self.assertTrue(any(f["rule_id"] == "TERM001" for f in report["findings"]))

    def test_vague_expression_is_review(self):
        report = analyze("必要に応じて処理する。", self.rules)
        self.assertEqual(report["issue_counts"]["REVIEW"], 1)
        self.assertFalse(fail_gate(report, "warn"))
        self.assertTrue(fail_gate(report, "review"))

    def test_number_and_unit_guard(self):
        changes = compare_preservation("処理時間は500ms。", "処理時間は600ms。", self.rules)
        self.assertTrue(any(x["rule_id"] == "PRESERVE001" for x in changes))

    def test_links_guard(self):
        changes = compare_preservation("[参考](https://example.com/a)", "[参考](https://example.com/b)", self.rules)
        self.assertTrue(any(x["rule_id"] == "PRESERVE001" for x in changes))

    def test_code_guard(self):
        changes = compare_preservation("```python\nx = 1\n```", "```python\nx = 2\n```", self.rules)
        self.assertTrue(any(x["rule_id"] == "PRESERVE002" for x in changes))

    def test_custom_protected_terms(self):
        rules = dict(self.rules, protected_terms=["Modbus-TCP"])
        changes = compare_preservation("Modbus-TCPを使用。", "UDPを使用。", rules)
        self.assertTrue(any(x["rule_id"] == "PRESERVE001" for x in changes))

    def test_fix_preserves_code_and_hard_break_and_is_idempotent(self):
        source = "# 見出し   \n本文  \n末尾に空白   \n```text\na   \n```\n"
        fixed = safe_fix(source)
        self.assertIn("本文  \n", fixed)
        self.assertIn("a   \n", fixed)
        self.assertIn("末尾に空白  \n", fixed)
        self.assertEqual(fixed, safe_fix(fixed))

    def test_no_semantic_autorewrites(self):
        source = "することができます。\n"
        self.assertEqual(source, safe_fix(source))

    def test_empty_document_is_error(self):
        report = analyze("```python\npass\n```", self.rules)
        self.assertEqual(report["issue_counts"]["ERROR"], 1)

    def test_rules_override_validates(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rules.json"
            p.write_text('{"sentence_warn_chars": 300}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_rules(override=str(p))

    def test_cli_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "doc.md"
            path.write_text("あ" * 170 + "。", encoding="utf-8")
            report = Path(d) / "report.json"
            self.assertEqual(main(["lint", str(path), "--format", "json", "--output", str(report), "--fail-on", "error"]), 1)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "1.0")
            self.assertTrue(data["findings"])

    def test_fixer_does_not_overwrite_existing_destination(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "a.md"
            target = Path(d) / "b.md"
            source.write_text("本文   ", encoding="utf-8")
            target.write_text("保護", encoding="utf-8")
            self.assertEqual(main(["fix", str(source), "--output", str(target)]), 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "保護")


if __name__ == "__main__":
    unittest.main()
