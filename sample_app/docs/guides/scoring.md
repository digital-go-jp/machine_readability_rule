# スコアリングアルゴリズム

## 概要

Harunobu のスコアリングは**決定論的**に行われます。同一の入力ファイルに対して常に同一の採点結果を返します（冪等性）。LLM による非決定論的な判定は行わず、通常のプログラムロジックで動作します。

AI 補完レイヤー（LLMマルチプロバイダー: Gemini / OpenAI / Anthropic）はオプショナルであり、有効な場合は信頼度（confidence）の向上に寄与しますが、スコア計算のロジック自体は決定論的ルールに基づきます。

実装: `sample_app/harunobu/core/scorer.py` / `sample_app/harunobu/core/severity.py`

## ルールの判定結果

各ルールの `check()` メソッドは `CheckResult` を返します。スコア計算に関係する主なフィールドは以下です。

| フィールド | 型 | 説明 |
|---|---|---|
| `passed` | bool | 合否（True = 合格） |
| `effective_severity` | Severity | 失敗時の重大度 |
| `confidence` | float | 信頼度（0.0 = 判定対象外、1.0 = 確実） |

ルール側は OK/NG と severity のみを返します。

## Severity（重大度）

```
FATAL > CRITICAL > MAJOR > MINOR > INFO
```

| Severity | スコアへの影響 |
|---|---|
| FATAL | 失敗するとそのレベルが**強制 0 点** |
| CRITICAL / MAJOR / MINOR | 失敗するとレベルから固定点数を減点 |
| INFO | 失敗してもスコアに影響なし（0 点減点） |

## レベルスコア

### 計算手順

1. `confidence == 0` のルール（未実行・エラー・判定対象外）を除外する
2. 有効なルールが 1 件もない場合、そのレベルのスコアは `None`（未チェック）
3. 有効なルールの中に FATAL 失敗があれば、そのレベルのスコアは **0**（強制 0 点）
4. それ以外は `max(0, 100 − 失敗ルールの固定減点合計)`

```
レベルスコア = max(0, 100 − Σ SEVERITY_DEDUCTIONS[(severity, level)])
```

### 固定減点テーブル

| Severity | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| CRITICAL | 10 | 40 | 15 |
| MAJOR | 5 | 30 | 10 |
| MINOR | 2 | 10 | 5 |
| INFO | 0 | 0 | 0 |

Level 2 の減点が大きいのは、対象ルール数が少ない（3 件）ためにルール 1 件あたりの重みを大きくする設計によります。

### 計算例

L1 で CRITICAL 1 件・MINOR 1 件が失敗した場合:

```
L1 スコア = max(0, 100 − 10 − 2) = 88
```

L2 で FATAL 1 件が失敗した場合:

```
L2 スコア = 0（強制 0 点）
```

## 複数ファイルの総合スコア（BulkAnalysisResult）

複数ファイルをまとめて評価する場合、ファイル横断チェック（Bulk ルール）の合格率も加味した加重平均になります。

```
ファイル別平均 = 各ファイルの総合スコアの平均
Bulk合格率   = (Bulk ルール合格数 / Bulk ルール有効数) × 100

総合スコア = round(ファイル別平均 × 0.7 + Bulk合格率 × 0.3)
```

Bulk ルールが存在しない、または有効な Bulk ルールが 0 件の場合は `ファイル別平均` をそのまま返します。

実装: `sample_app/harunobu/rules/bulk_base.py` `BulkAnalysisResult.total_score`

## 集計粒度

`LevelScorer` は 3 つの粒度でスコアを算出できます。

| メソッド | 単位 | 用途 |
|---|---|---|
| `score_mr_result(mr_result)` | 1 テーブル | テーブル単位の評価 |
| `score_sheet_result(sheet_result)` | 1 シート（複数テーブル） | データシートのみを採点したい場合（注釈シート・グラフ用シートを除外） |
| `score_analysis(analysis)` | ファイル全体 | 通常の採点（JSON 出力・UI でもこれを使用） |

## 判定不能時の挙動

### ルール未実行（confidence = 0）

以下の場合、ルールの confidence が 0 に設定され、スコア計算から除外されます。

- **対象外フォーマット**: CSV ファイルに対する Excel 専用ルール（L1-10, L1-11, L1-12, L1-13, L2-06）、Excel ファイルに対する CSV 専用ルール（L1-14, L1-15）
- **ルール実行時のエラー**: 予期しない例外が発生した場合
- **対象データなし**: チェック対象となるデータが存在しない場合
- 判定対象外ルール: L3-02 などHarunobuにおいて判定対象外としたルール

### AI 補完が利用不可

AI 補完レイヤー（`AISemanticChecker` / `AIVisualAnalyzer`）が利用できない場合:

- スコア自体は決定論的ルールで計算されます
- AI に依存するルール（L1-11, L2-02 等）では confidence が低下します
- `HARUNOBU_AI_DISABLED=1` で明示的に無効化可能（テスト・オフライン環境向け）

### レイアウト推定失敗

レイアウト推定（IslandDetector）がテーブルを検出できなかった場合:

- テーブル検出数が 0 件となります
- 全ルールの confidence が 0 となり、スコア計算から除外されます
- 全レベルのスコアが `None`（未チェック）となります
