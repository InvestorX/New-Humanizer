---
name: japanese-writing-quality
description: LLMに判断を丸投げせず、日本語Markdown・テキストの文長、冗長表現、見出し、用語揺れ、数値・引用の保全をPythonで検査する。文章の作成・修正・設計書レビュー・品質ゲートに使う。
---

# Japanese Writing Quality (deterministic first)

## 原則

- 本スキルで検証可能な品質基準は **Pythonの実行結果が唯一の判定根拠**。LLMの自己評価を合格条件として代用しない。
- `SKILL.md` は作業手順書であり、検査エンジンではない。`python -m jp_writing_quality` が検査・比較・自動修正の主体。
- LLMによる文章の言い換え・圧縮は任意。事実の取捨選択、指示対象、因果関係はコードでは保証できない。
- ERRORが残れば **未合格** と伝える。WARNも厳格運用時はゲート対象にする。REVIEWは人間の要確認事項であり、合格＝理解しやすい証明ではない。
- 数字・単位・URL・リンク先・脚注・インラインコード・コードブロック・指定保護語は変更前後で機械比較する。差分が生じたら人間の承認を得る。
- ルール閾値は研究による普遍的な「認知負荷スコア」ではなく、チームで調整するヒューリスティック。

## 依存環境

Python 3.10以上。追加Pythonパッケージ不要。スキルのルート（本 `SKILL.md` のあるフォルダ）で実行する。

## 作業の流れ

1. `source.md` を保存する。Markdownとプレーンテキストをサポート（UTF-8）。
2. `python -m jp_writing_quality lint source.md --profile technical --format json --output quality-before.json --fail-on warn` を実行し、終了コードを確認する。
3. 必要なら `python -m jp_writing_quality fix source.md --output formatted.md` で**行末空白のみ**安全な範囲で修正する。出力diffを確認する。
4. 内容の改善が必要なら、LLMは `quality-before.json` の指摘箇所だけを修正候補として提案する。無断で数字・単位・名称・出典・API識別子・コード・意味を変更しない。修正候補は別ファイル `revised.md` へ保存する。
5. `python -m jp_writing_quality compare source.md revised.md --profile technical --format json --output quality-after.json --fail-on warn` で修正版と原文の両方に依存する検証を実行する。
6. `python -m unittest discover -s tests -v` でエンジン自体の回帰テストを実行する。
7. 最終報告では、検査結果（ERROR/WARN/REVIEW数）、変更差分、保全チェック、未検証項目とレビュー必要箇所を提示する。合格しない場合は完了宣言をしない。

## 使用するコマンド

```bash
# 読みやすさの機械検査
python -m jp_writing_quality lint document.md --profile general --format text --fail-on warn

# JSON監査証跡
python -m jp_writing_quality lint document.md --profile technical --format json --output report.json

# 意味変更を伴わない書式修正（入力は保持）
python -m jp_writing_quality fix document.md --output document.fixed.md

# 原文と修正案の保護要素の整合性をチェック
python -m jp_writing_quality compare document.md document.fixed.md --profile technical --format markdown --output comparison.md

# チームごとの閾値上書き
python -m jp_writing_quality lint document.md --rules my-rules.json --fail-on warn
```

## 機械判定されるルール

| ID | 検査 | 原則 | 判定 |
| --- | --- | --- | --- |
| DOC001 | 本文が存在するか | 本文なし | ERROR |
| SENT001 | 一文の文字数 | profileで閾値指定 | WARN/ERROR |
| PUNCT001 | 一文の読点数 | profileで閾値指定 | WARN |
| PARA001 | 長すぎる段落 | profileで閾値指定 | WARN |
| DUP001 | 同一段落の反復 | 20文字以上の一致 | WARN |
| STYLE001 | 冗長な定型表現 | 辞書一致 | WARN |
| VAGUE001 | 曖昧な定型表現 | 辞書一致。文脈の善悪は判定しない | REVIEW |
| TERM001 | 用語の表記揺れ | 複数候補が混在 | WARN |
| HEAD001 | 見出し階層の飛び | #のレベル差 | WARN |
| HEAD002 | 長文の冒頭に概要等がない | technicalで有効 | WARN |
| PRESERVE001 | 数字・単位・リンク・引用・保護語・インラインコードの差分 | 原文と修正版のカウント比較 | ERROR |
| PRESERVE002 | Markdownコードブロックの差分 | 原文と修正版の完全一致 | ERROR |

## LLMを使う場合の局所修正指示

> PythonのJSON指摘箇所だけを修正案として提示してください。内容の削除・追加・言い換えは意味が変わり得るため、根拠と差分を示してください。数値・単位・URL・出典・固有名詞・API名・コード・技術要件は維持してください。修正後は必ずPythonの `compare` を実行し、ERROR/WARNが残る場合は合格を宣言しないでください。`REVIEW` は人間の確認事項として残してください。

## 対象外と限界

- 日本語の品詞解析・係り受け解析、係り先の意味、要件漏れ、論理の正しさ、根拠の正確性、事実性は検証しない。
- 数値等の一致は**形式的なガード**。数字が同じでも対応関係を入れ替えた場合は検知できない。固有名詞は事前に `protected_terms` に設定した語に限る。
- Markdown表、コード、YAML front matter、インラインコードは原則として文長検査の対象外。改行を含む文章の位置表示は段落開始行を示す場合がある。
- `fix` は文章の意味を書き換えないため、文長・冗長表現の検査指摘は自動では解消しない。
- 機械チェックのPASSは、人間による理解度・読了時間・認知負荷の実測を代替しない。

## 出力品質の確認

- JSONレポートとCLIの終了コードが一致すること。
- 数値・コードを変更した偽の修正版が `compare` でERRORになること。
- `fix` の2回実行で出力が同一になること（冪等性）。
- 保護対象に一切変更がなくても、意味保存は人間が必要に応じて確認すること。
