# New-Humanizer

**AI製ドキュメントによる読み疲れからの解放**

## 日本語文章の品質チェック


**日本語ドキュメントの機械的品質チェックを行う、LLM不要・Python標準ライブラリのみのAgent Skillです。**

文章の「認知負荷」を直接測定するものではありません。**検査可能な形式品質**（文長、読点、段落長、定型表現、表記揺れ、見出し階層、修正前後の保護対象の差分）を再現可能にチェックします。

検査結果には漢字・カタカナ率も**参考統計**として付けます（合否には使用しません）。`schema/quality-report.schema.json` にJSONレポートの構造を示しています。

## すぐに使う

Python 3.10+ を用意し、本フォルダで実行してください。`pip install` は不要です。

```bash
# サンプルの品質検査（合否の閾値は--fail-onで選択）
python -m jp_writing_quality lint fixtures/verbose.md --profile technical --format text --fail-on warn

# JSONレポートをファイルに出力
python -m jp_writing_quality lint fixtures/verbose.md --format json --output quality.json

# 原文を変更せずに、安全な書式修正と差分を表示
python -m jp_writing_quality fix fixtures/verbose.md --output verbose.fixed.md

# 修正後に数値、URL、コード、出典等が消えていないか比較
python -m jp_writing_quality compare fixtures/verbose.md fixtures/revised.md --profile technical --format json --output comparison.json

# 回帰テスト
python -m unittest discover -s tests -v
```

CLIをインストールして使いたい場合は、オプションで `pip install -e .` を実行し、`jp-writing-lint lint ...` を使えます（ビルドツールが必要になる場合があります）。

**終了コード:** `0` = 指定ゲートPASS、`1` = ルール違反でゲートFAIL、`2` = コマンドまたは入出力エラー。

## ファイル構成

```text
japanese-writing-quality-skill/
├── SKILL.md                        # エージェント用の品質保証手順
├── README.md
├── pyproject.toml
├── LICENSE
├── jp_writing_quality/
│   ├── cli.py                      # lint / fix / compare
│   ├── analyzer.py                 # 決定的なルールと保全照合
│   ├── parser.py                   # Markdown本文の抽出
│   ├── fixer.py                    # 書式に限る安全修正
│   └── rules/
│       ├── general.json           # 一般向け基準
│       └── technical.json         # 技術文書向け基準
├── fixtures/
└── tests/
```

## ルール変更

プロファイルに組み込まれた数値は、研究で検証された「認知負荷の閾値」ではなく**調整可能な初期値**です。技術ドキュメントには `--profile technical` を使ってください。

```json
{
  "sentence_warn_chars": 80,
  "sentence_error_chars": 140,
  "max_commas": 4,
  "protected_terms": ["Azure", "PostgreSQL", "Modbus-TCP"]
}
```

このJSONを `team-rules.json` に保存すれば次のように使えます。

```bash
python -m jp_writing_quality lint example.md --profile technical --rules team-rules.json --fail-on warn
python -m jp_writing_quality compare original.md revised.md --profile technical --rules team-rules.json --fail-on error
```

`compare` は数字・単位、URL、Markdownリンク先、脚注参照、インラインコード、コードブロック、指定した `protected_terms` を照合します。**数字が一致していても意味や対応先が同じである保証はありません。** 内容の正確さは人によるレビューが必要です。

## Claude Code / Agentでの導入

`SKILL.md` とPythonソース一式を、エージェントが参照しPythonを実行できる場所に配置してください。Claude Codeでプロジェクトスキルとして使う場合は `./.claude/skills/japanese-writing-quality/` にフォルダごと配置する方法があります。`SKILL.md` の指示どおり、**実際のCLIを動かしてレポートを提示**させてください。エージェントがコード実行できない環境では品質ゲートを満たせません。

## 制限事項

- 自然さ、因果関係、固有名詞の完全な保全、要件の網羅性、読者の真の認知負荷は評価しません。
- Markdownの複雑な構文の一部や表・コードなどを意図的に検査対象から除外しています。
- `fix` は末尾の不要な空白の除去のみ行います。Markdownの2スペース改行とコードブロックは保持します。
- 原文と修正案の比較は同一ファイルの改稿を想定しています。コードや引用の意図的変更も検出します。
