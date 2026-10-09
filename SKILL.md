---
name: japanese-writing-quality
description: Check Japanese Markdown or plain text with reproducible Python lint, safe formatting, and content-preservation comparison. Use when drafting, revising, or reviewing Japanese documents and when an agent must report verifiable writing-quality findings.
---

# Japanese Writing Quality

## Purpose

This skill coordinates a deterministic Python checker for Japanese writing. **Use the CLI results, not an LLM's subjective judgment, as the evidence for machine-checkable quality gates.**

The checker identifies measurable indicators of potential reading difficulty; it **does not** directly measure cognitive load, validate meaning, or prove that readers will understand a document.

## Working assumptions

- **Runtime:** Python 3.10 or later; no third-party Python packages are required to run the CLI.
- **Root directory:** execute commands from the directory containing this `SKILL.md` and the `jp_writing_quality/` package, or otherwise ensure the package is on Python's import path.
- **Inputs:** UTF-8 Japanese Markdown or plain-text files.
- **Profiles:** use `general` for broad-audience documents and `technical` for specifications, engineering notes, and other technical material.
- **Rules:** use `--rules path/to/team-rules.json` to override the selected profile, when needed.
- **Language:** this skill's instructions are in English; the checked document and the CLI's findings may be in Japanese.

## Required workflow

1. **Preserve the source.** Save the initial draft as `original.md`; do not discard it during revisions.
2. **Run a baseline check.** Execute `lint` with a suitable profile and capture the JSON report **and the process exit code**.
3. **Review findings.** Prioritize `ERROR`, then `WARN`. Investigate `REVIEW` findings in context; they are not automatically incorrect.
4. **Apply only safe mechanical fixes automatically.** The `fix` command removes unnecessary trailing whitespace; it deliberately preserves Markdown hard breaks and code blocks. Inspect its diff.
5. **Suggest any substantive edits explicitly.** An LLM may simplify sentence structure or remove redundant wording, but changes to requirements, facts, causal relationships, references, technical identifiers, or named entities need careful review. Save candidate changes in a separate file such as `revised.md`.
6. **Compare with the original.** Execute `compare original.md revised.md`. Treat any `PRESERVE001` or `PRESERVE002` finding as a **blocking preservation failure**, unless a human expressly approves the changed material.
7. **Re-run the quality gate.** A `compare` report also analyzes the revised text. Optionally run `lint` directly on the final document for a standalone report. Never claim a passing gate when its command has not been executed or returned a failing status.
8. **Report results.** Include the selected profile, rule overrides, gate threshold, `ERROR`/`WARN`/`REVIEW` counts, exit code, outstanding risks, and changes requiring human approval. If execution was unavailable, state that checks were **not run**.
9. **Test engine changes.** If the Python checker, fixtures, or rules are modified, run the regression suite. Routine writing reviews do not need to rerun the engine's tests.

## Commands

Run from the skill/project root:

```bash
# Lint a general-audience document.
python -m jp_writing_quality lint document.md --profile general --format text --fail-on warn

# Write a JSON report; use the process exit code to decide whether the gate passed.
python -m jp_writing_quality lint original.md --profile technical --format json --output quality-before.json --fail-on warn

# Apply whitespace-only formatting to a new file; original.md stays unchanged.
python -m jp_writing_quality fix original.md --output formatted.md

# Analyze a revision and compare protected elements with the original.
python -m jp_writing_quality compare original.md revised.md --profile technical --format json --output quality-after.json --fail-on warn

# Use a team-specific rules file.
python -m jp_writing_quality lint document.md --profile technical --rules team-rules.json --fail-on warn

# Run tests after modifying the checker itself.
python -m unittest discover -s tests -v
```

The CLI exits with `0` when the chosen gate passes, `1` when findings fail the gate, or `2` on command/configuration/I/O errors. Choose the gate via `--fail-on none|error|warn|review`; `warn` blocks on `WARN` and `ERROR`, while `review` also blocks on `REVIEW`.

**Do not overwrite the input** unless the user requests it: `fix` requires `--output` or an explicit `--in-place`. It will refuse to overwrite an existing different output file.

## Built-in checks

| Rule | What it checks | Severity |
| --- | --- | --- |
| `DOC001` | Missing prose content | ERROR |
| `SENT001` | Excessive sentence length based on profile thresholds | WARN / ERROR |
| `PUNCT001` | Too many Japanese commas in a sentence | WARN |
| `PARA001` | Excessive paragraph length | WARN |
| `DUP001` | Repeated text within a paragraph | WARN |
| `STYLE001` | Known verbose expressions | WARN |
| `VAGUE001` | Potentially vague expressions, without judging the context | REVIEW |
| `TERM001` | Inconsistent forms of specified terms | WARN |
| `HEAD001` | Skipped Markdown heading levels | WARN |
| `HEAD002` | Missing overview-type opening in long technical documents | WARN |
| `PRESERVE001` | Changes in protected numbers/units, URLs, links, references, inline code, and configured terms | ERROR |
| `PRESERVE002` | Changes in fenced code blocks | ERROR |

The thresholds are configurable **heuristics**, not research-validated universal measures of cognitive load. Do not combine these checks into an invented scientific readability score.

## If an LLM proposes a rewrite

Use this editing constraint:

> Make targeted suggestions for the passages identified in the JSON findings. Preserve the document's facts, requirements, names, quantities, units, URLs, citations, technical identifiers, and code. Explain substantive edits and provide a diff. Do not assume that a mechanically passing report proves semantic equivalence. Run `compare` after revising, and surface unresolved `REVIEW` items for human inspection.

## What the checker cannot guarantee

- Truthfulness, logical coherence, causality, coverage of requirements, or quality of evidence.
- Semantic preservation when numbers or terms are rearranged but their counts remain unchanged.
- Full preservation of proper nouns unless they are listed as `protected_terms`.
- Syntactic or semantic analysis of all Japanese constructions.
- Accurate interpretation of complex Markdown tables, mixed prose/code, or every reference convention.
- Reader comprehension, reading time, or actual cognitive load.

A **machine-check pass** is evidence that selected *mechanical rules* passed; it is not a substitute for human review. See [README.md](README.md) and [README.ja.md](README.ja.md) for usage details.

## License

This project is released under **THE SUSHI-WARE LICENSE**. Retain the notice when copying or redistributing this skill and its scripts. See [LICENSE](LICENSE).
