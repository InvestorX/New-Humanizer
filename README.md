# New-Humanizer

**Less reading fatigue from AI-generated documents.**

[English](README.md) | [日本語](README.ja.md)

New-Humanizer is an Agent Skill and a **deterministic, Python-based writing-quality checker for Japanese Markdown and plain text**. It helps agents and authors detect *measurable writing issues* rather than relying solely on an LLM's subjective self-assessment.

It does **not** directly measure cognitive load or guarantee that a document is easy to understand. Its configurable checks identify possible readability issues such as long sentences, excessive punctuation, lengthy paragraphs, repeated phrasing, inconsistent terminology, and heading structure. The tool also checks whether certain protected content changed between drafts.

- **Zero runtime dependencies:** Python 3.10+ standard library only.
- **Reproducible:** configurable general/technical profiles and structured findings with severity levels.
- **Safe-by-default edits:** the `fix` command only removes trailing whitespace while preserving Markdown hard breaks and fenced code blocks.
- **Content safeguards:** the `compare` command detects changes to numbers/units, URLs, Markdown link destinations, reference markers, code, and explicitly configured protected terms.
- **Auditable:** CLI exit codes, JSON output, a JSON report schema, fixtures, tests, and GitHub Actions.

> **Scope:** These are heuristic writing-quality checks, not scientifically validated cutoffs for human cognitive load. Treat `REVIEW` findings as prompts for human judgment, not proven errors.

## Quick start

Run the commands from the repository root with Python 3.10 or newer. No installation is required.

```bash
# Inspect a Japanese Markdown document; make WARN findings fail the gate.
python -m jp_writing_quality lint fixtures/verbose.md --profile technical --format text --fail-on warn

# Write a machine-readable JSON report.
python -m jp_writing_quality lint fixtures/verbose.md --format json --output quality.json

# Apply safe formatting changes to a new file, leaving the source untouched.
python -m jp_writing_quality fix fixtures/verbose.md --output verbose.fixed.md

# Inspect the revised document and check preservation of protected content.
python -m jp_writing_quality compare fixtures/verbose.md fixtures/revised.md --profile technical --format json --output comparison.json

# Run the regression test suite.
python -m unittest discover -s tests -v
```

Optional editable installation (may need a build backend):

```bash
pip install -e .
jp-writing-lint lint fixtures/verbose.md --profile technical
```

**Exit codes:** `0` = selected quality gate passed; `1` = findings triggered the selected quality gate; `2` = command, configuration, or I/O error.

## Repository layout

```text
New-Humanizer/
├── README.md                         # English documentation (default)
├── README.ja.md                      # Japanese documentation
├── SKILL.md                          # English instructions for AI agents
├── pyproject.toml
├── jp_writing_quality/
│   ├── cli.py                        # lint, fix, compare
│   ├── analyzer.py                   # deterministic checks and preservation guards
│   ├── parser.py                     # Markdown/text extraction
│   ├── fixer.py                      # safe whitespace-only fixes
│   └── rules/
│       ├── general.json              # general writing profile
│       └── technical.json            # technical writing profile
├── fixtures/                          # positive/negative examples
├── examples/                          # example JSON reports
├── schema/                            # JSON report schema
├── tests/                             # regression tests
└── .github/workflows/quality.yml     # CI checks
```

## Profiles and custom rules

Use `--profile general` for general writing and `--profile technical` for technical documentation.

Numeric thresholds in the built-in profiles are **adjustable defaults**, not universal cognitive-load thresholds. To override them, create a JSON file such as `team-rules.json`:

```json
{
  "sentence_warn_chars": 80,
  "sentence_error_chars": 140,
  "max_commas": 4,
  "protected_terms": ["Azure", "PostgreSQL", "Modbus-TCP"]
}
```

```bash
python -m jp_writing_quality lint document.md --profile technical --rules team-rules.json --fail-on warn
python -m jp_writing_quality compare original.md revised.md --profile technical --rules team-rules.json --fail-on error
```

The checker reports issues as **ERROR**, **WARN**, or **REVIEW**. Select the quality-gate strictness with `--fail-on none|error|warn|review`. A `review` threshold is the strictest; a `none` threshold never fails on findings.

## Using the Agent Skill

Keep `SKILL.md` together with the Python package and configuration files. An agent needs **both** the skill instructions and an environment in which it can run Python.

For example, a Claude Code project-local skill can be placed in `.claude/skills/japanese-writing-quality/`. Copy the complete project content needed by the CLI, not only `SKILL.md`. See [SKILL.md](SKILL.md) for the agent workflow.

A typical workflow is:

1. Save the original Japanese document.
2. Run `lint`, inspect its output and exit status.
3. Apply safe formatting or propose targeted wording changes.
4. Run `compare` against the original and recheck the revised document.
5. Report remaining findings and any changes that need human approval.

**Do not claim a quality-gate pass without executing the CLI.** In an environment without code execution, the agent can make suggestions but cannot verify a deterministic gate.

## Limitations

- The tool does not verify factual accuracy, reasoning, causal relationships, completeness of requirements, or actual reader comprehension.
- The preservation check compares protected elements (including counts and code blocks), **not their semantic relationships**. Keeping the same numbers does not guarantee that they still refer to the same facts.
- Complex Markdown, tables, inline code, and fenced code blocks are partly or intentionally excluded from readability checks.
- The safe fixer only removes trailing whitespace; it does not automatically rewrite long or vague sentences.
- Kanji and katakana ratios are provided as descriptive statistics, **not pass/fail criteria**.
- The CLI's issue messages are primarily in Japanese because the documents it analyzes are Japanese.

## License

**THE SUSHI-WARE LICENSE** 🍣 — you may use, modify, and redistribute this project as long as you retain the license notice. If we ever meet and you find it worthwhile, you can buy me sushi (entirely optional).

See the full [LICENSE](LICENSE) text.
