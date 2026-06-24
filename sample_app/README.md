# 機械可読性ルール判定 サンプルアプリ

このツールは「行政データにおける機械可読性に関するルール」に基づき、Excel/CSVファイルについてルールに照らし合わせた採点を行うシステムのサンプル実装アプリです。

サンプル実装アプリの開発はデジタル庁Fact & Data Unitが行いました。
ルールに基づいたExcelファイルの判定、修正などを行うシステム開発時の参考としてご利用ください。
以後、当サンプル実装アプリを開発名である `Harunobu` と呼称します。

## 機械可読性ルール判定　サンプルアプリ「Harunobu」の機能

判定対象となるExcel/CSVファイルについて、機械可読性ルールに従い、決定論的に機械可読性を100点満点で採点します。（AI補完オプションあり）
採点は機械可読性ルールのレベルごとに行われ、採点結果はレベル１で100点、レベル2で40点、レベル3で0点のように出力されます。
採点結果は各レベルで満たすべき基準にどの程度満たせているかを測る基準としてご利用ください。
サンプルアプリ Harunobu においては、各ルールの重大度をFATAL, CRITICAL, MAJOR, MINORと定めて配点を決定しています。
ルールごとの配点表は [ルール配点表](docs/rule_scoring_table.csv) をご確認ください。

レベルごとの採点結果を表示する他、下記を含む結果ファイルを出力することができます。

* データ領域を推定するレイアウト推定の結果
* ルール違反があった箇所一覧
* 違反したルールと違反理由

結果ファイルはExcel/CSVファイルを修正して機械可読性を向上させる目的で参照する他、AI等で修正作業を効率化する際のAIへの指示書としても活用されることを想定しています。
結果ファイルはJSON 形式、またはCSV 形式で出力することができます。
違反箇所が多い場合、CSV 形式では違反結果の一部がまとめられて出力されることがあります。
JSON 形式の場合は違反箇所の数に関わらず、全ての違反箇所が結果ファイルに含まれます。

詳細な結果ファイルのフォーマットについては [出力フォーマット](docs/guides/output-format.md) をご確認ください。

これらの機能を利用する方法は以下の3つです。

- CLI — コマンドラインから Excel/CSV を採点し、JSON/CSV 形式で結果を出力します。
- Streamlit UI — ブラウザ上でファイルをアップロードして採点結果を確認します。
- Python API — プログラムから直接採点パイプラインを呼び出せる組み込みインターフェースとして機能します。

## 動作環境

| 項目 | 要件 |
|------|------|
| OS | Windows / macOS / Linux |
| Python | 3.10 以上 |
| メモリ | 1 GB 以上（大規模ファイル処理時は2 GB以上を推奨） |

利用にあたって必要なライブラリなどの詳細情報は [THIRD-PARTY-NOTICE.txt](./THIRD-PARTY-NOTICE.txt) を参照してください。

> AI補完機能を有効にする場合は、Gemini / OpenAI / Anthropic 等のマルチプロバイダーに対応した API キー（または Vertex AI 環境）が必要です。詳しくは [AI設定ガイド](docs/guides/ai-configuration.md) を参照してください。

pythonのパッケージマネージャーは `uv` を使用しています。
uvのインストール方法についてはuv公式のスタンドアロンインストーラーを利用してのインストールを推奨しています。

**Windows:**

```shell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Mac OS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

※ `python pip install .` でもインストールできますが、パッケージの厳密なバージョン固定がされない点にご留意ください。

## Streamlit UI 利用方法

ここではブラウザ上でファイルをアップロードするWEBアプリとしてHarunobuを起動する場合の利用方法を記載します。

### Docker（推奨）

```bash
docker build -t harunobu .
docker run -p 8080:8080 harunobu
```

http://localhost:8080 でアクセス。

### ローカルから起動

```bash
uv sync --extra ui
uv run streamlit run app.py
```

### Streamlit UI 動作フロー

```
UPLOAD → PREVIEW → VALIDATION → SCORING → RESULT
```

1. **UPLOAD**: Excel(.xlsx/.xlsm)/CSV/TSV ファイルをアップロード
2. **PREVIEW**: シート選択して採点対象データをプレビュー表示
3. **VALIDATION**: レイアウト（データの入った表領域）の検出結果を表示
4. **SCORING**: 採点モードを選択（lite/standard/thorough）し、採点を実行
5. **RESULT**: スコア表示、違反箇所の提示、採点結果のまとめJSON/CSVファイルをダウンロード

採点モードによって対象となるルールのレベルが異なります。ルールとの対応は以下の通りです。

| モード | 対象レベル | 用途 |
|--------|-----------|------|
| `lite` | L1 のみ | 簡易チェック |
| `standard` | L1 + L2 | 通常利用（デフォルト） |
| `thorough` | L1 + L2 + L3 | 詳細分析 |

詳細なStreamlit UIの操作方法については [UI操作マニュアル](docs/guides/user-manual-ui.md) をご確認ください。

## CLI 利用方法
### インストール方法

以下のいずれかの方法で利用可能です。

1: 本リポジトリ内で起動する場合

```bash
uv sync
```

2: ライブラリとしてインストールして起動する場合

```bash
uv pip install "harunobu @ git+https://github.com/digital-go-jp/machine_readability_rule.git#subdirectory=sample_app"

# AI補完機能も使用する場合
uv pip install "harunobu[ai] @ git+https://github.com/digital-go-jp/machine_readability_rule.git#subdirectory=sample_app"
curl -o .env https://raw.githubusercontent.com/digital-go-jp/machine_readability_rule/refs/heads/main/sample_app/.env.example
```

3: PEP 723 形式でスクリプト内に依存を埋め込む場合:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "harunobu @ git+https://github.com/digital-go-jp/machine_readability_rule.git#subdirectory=sample_app",
# ]
# ///
```

### CLIの使い方

```bash

# Excel ファイルを採点（JSON出力）
uv run harunobu analyze data.xlsx

# 採点モードを指定
uv run harunobu analyze data.xlsx --mode thorough

# 採点結果をJSON 形式で標準出力
uv run harunobu analyze data.xlsx --output json

# ファイルに保存
uv run harunobu analyze data.xlsx --out-path result.json
```

## Python API 利用方法

ライブラリとしてインストールした場合は、以下のようにPythonのスクリプトから利用できます。

```python
from pathlib import Path

from harunobu import AnalysisResult, Config, analyze
from harunobu.core.models import CheckResult
from harunobu.core.scorer import LevelScorer, LevelScoring

# analyze() → AnalysisResult: ファイル全体の採点結果（シート → テーブル → ルール）
result: AnalysisResult = analyze(Path("data.xlsx"), Config())

# score_analysis() → LevelScoring: L1/L2/L3 ごとの LevelScore（per_level: dict[int, LevelScore]）
scorer = LevelScorer()
scoring: LevelScoring = scorer.score_analysis(result)
for level, level_score in scoring.per_level.items():
    print(f"L{level}: {level_score.score} 点 ({level_score.passed}/{level_score.total} ルール合格)")

# all_results() → dict[str, CheckResult]: rule_id ごとの OK/NG・confidence・violations 等
for sheet in result.sheets:
    for table in sheet.tables:
        rule_results: dict[str, CheckResult] = table.mr_result.all_results()
        for rule_id, check in rule_results.items():
            print(f"{rule_id}: {'OK' if check.passed else 'NG'} (confidence: {check.confidence:.2f})")
```


## ディレクトリ構成

```
sample_app/
├── app.py                 ← エントリーポイント（Streamlit）
├── Dockerfile
├── pyproject.toml
├── .streamlit/            ← Streamlit設定（config.toml: テーマカラー等）
├── harunobu/              ← パッケージ本体
│   ├── __main__.py        ← CLIエントリーポイント（harunobu analyze）
│   ├── core/              ← 採点パイプライン（Reader, Analyzer, AI補完）
│   │   └── layout/        ← レイアウト検出（LayoutDetector, IslandDetector）
│   ├── rules/             ← ルールプラグイン（30ルール、各1ファイル = 1クラス）
│   ├── output/            ← JSON/CSV出力
│   ├── resources/         ← 内蔵リソース（出力スキーマJSON、地域辞書等）
│   └── ui/                ← Streamlit UI（5ページ + コンポーネント）
└── tests/                 ← テスト（core/ rules/ integration/ output/ ui/ sample_by_mr_rules/）
```

## 本リポジトリへのコントリビューション: Issue / Pull Request の対応方針について

本リポジトリのコントリビューションについては、サンプル実装アプリ部分（`sample_app/`）へのIssue のみ受け付けています。Pull Request は受け付けておりません。また、質問・使い方の相談等でIssue 報告を行うことはご遠慮ください。

### Issueの対応について

Issue への対応は、内部の優先度判断に基づき行います。
そのため、すべての Issue に対応できるとは限りません。
また、対応状況についてのお問い合わせへの個別回答は行っておりません。
致命的と判断された問題については、可能な範囲で対応状況を Issue 上でお知らせします。

### 脆弱性の報告

脆弱性の報告については[セキュリティポリシー](../SECURITY.md) よりご報告ください。

## コミュニティガイドライン

このリポジトリ（ソースコードおよびドキュメント）は、デジタル庁が作成し、公開するものです。
公的資源として、OSS コミュニティのすべての方にオープンにしております。そのため、以下のことを禁止します。

* 特定の思想・団体・企業を支持または排除するような行為
* 政治的・宗教的・差別的・ハラスメントとなる内容の発言
* 個人情報や機微情報をリポジトリ上で扱う行為
* セキュリティ脆弱性発見時に、デジタル庁に報告・承諾を得ることなく、脆弱性内容を第三者に開示する行為
* 本ソースコードを他システムへの攻撃を目的として改変する行為

## 免責事項

* 本ソフトウェアの使用は、利用者自身の責任において行われるものとします。
* 本ソフトウェアの提供にあたり、不具合の修正や機能改善の義務を負うものではありません。

### 行政データにおける機械可読性に関するルールについて

* 各ルールは今後の検討により変更される可能性があります。
* 本ソフトウェアでは一部のルールについて判定対象外としています。
* 本ソフトウェアで実装されている各ルールごとのスコアリングの配点や、その判定ロジックについては、あくまでサンプル実装として本ソフトウェアで独自に開発されたものであり、政府の公式見解を示すものではありません。
* その他、採点対象ファイルのレイアウトを推定する機能や、AIによるルール判定の補完についても、その動作の正確性、完全性、妥当性を保証するものではありません。

ルール判定について詳細な制限事項については [既知の制限事項](docs/guides/limitations.md) をご確認ください。


## ライセンスについて

* 行政データにおける機械可読性に関するルールを記載した以下のファイル及び各種ドキュメントファイル（.md）については、[公共データ利用規約第1.0版（PDL1.0）ライセンス](../LICENSE.md)が適用されます。
  * [machine-redability-rules.json](../machine-readability-rules.json)
  * [machine-redability-rules.csv](../machine-readability-rules.csv)
* サンプル実装アプリ部分（`sample_app/`）には[MITライセンス](../LICENSE-MIT.md)が適用されます。
