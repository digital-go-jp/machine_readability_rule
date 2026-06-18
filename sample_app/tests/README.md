# テストコード

## ディレクトリ構成

```
tests/
├── conftest.py              # ルートレベルfixture（rules/conftest.pyの再エクスポート）
├── test_layout_header_detection.py
├── rules/                   # ルールごとのユニットテスト
│   ├── conftest.py          # ルールテスト共通fixture（create_workbook, create_context）
│   ├── L1_01_file_format/
│   │   ├── __init__.py
│   │   └── test_check.py
│   ├── L1_02_one_table_per_sheet/
│   │   └── ...
│   └── ... （全30ルール分）
├── core/                    # コア機能のテスト
│   ├── test_analyzer.py
│   └── ...
├── output/                  # 出力writerのテスト
│   └── test_writer_violation_summary.py
├── resources/               # テスト用リソース
│   └── test_region_dict.py
├── integration/             # 統合テスト
│   ├── sample_rules/        # sample_by_mr_rulesのサンプルを使ったルール検証
│   │   └── conftest.py      # sample_rules固有fixture（collect_samples等）
│   ├── test_pipeline.py
│   ├── test_output.py
│   └── ...
├── sample_by_mr_rules/      # ルール別サンプルデータと生成スクリプト
│   ├── README.md
│   ├── generate_test_data.py
│   ├── sample_generators/
│   └── samples/
└── ui/                      # UI E2Eテスト
    ├── conftest.py
    ├── fixtures/
    │   └── test_data.xlsx
    └── ...
```

## テストの実行

```bash
cd app

# 全テスト実行
uv run pytest

# 特定ルールのテスト
uv run pytest tests/rules/L1_12_merged_cells/

# 特定のテスト関数
uv run pytest tests/rules/L1_12_merged_cells/test_check.py::test_no_merged_cells

# verbose出力
uv run pytest -v

# annotation_tracker マーカーのテスト（改善トラッキング用、通常はスキップ）
uv run pytest -m annotation_tracker

# sample_by_mr_rules のサンプルデータを再生成
uv run tests/sample_by_mr_rules/generate_test_data.py

# 指定ルールだけサンプルデータを再生成
uv run tests/sample_by_mr_rules/generate_test_data.py --rules 8
```

`annotation_tracker` マーカーは `pyproject.toml` に登録済み。
`generate_test_data.py` は PEP 723 metadata で Python 3.12+ と追加依存を宣言しており、`uv run` がそれらを解決。

## テストfixture

### `create_workbook` fixture

```python
def test_example(create_workbook):
    wb = create_workbook(
        sheets_data={
            "Sheet1": [
                ["ID", "名前", "値"],    # 1行目: ヘッダー
                [1, "項目A", 100],        # 2行目以降: データ
                [2, "項目B", 200],
            ]
        },
        file_name="test.xlsx",
        merged_cells=[
            {"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 1, "end_col": 2}
        ],
        hidden_rows={"Sheet1": [3]},
        hidden_cols={"Sheet1": [2]},
        formulas={"Sheet1": {(2, 3): "=SUM(A2:B2)"}},
    )
```

### `create_context` fixture


```python
def test_rule(create_context):
    context = create_context(
        sheets_data={
            "Sheet1": [
                ["ID", "値"],
                [1, 100],
                [2, 200],
            ]
        },
        stub_cols=[1],
    )
    rule = SomeRule()
    result = rule.check(context)
    assert result.passed
    assert result.score == 100
```

### パラメータ一覧

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `sheets_data` | `dict[str, list[list[Any]]]` | シート名→行データのマッピング。必須。 |
| `file_name` | `str` | ファイル名（拡張子でフォーマット判定）。デフォルト: `"test.xlsx"` |
| `merged_cells` | `list[dict]` | 結合セル情報のリスト |
| `hidden_rows` | `dict[str, list[int]]` | シート名→非表示行番号リスト |
| `hidden_cols` | `dict[str, list[int]]` | シート名→非表示列番号リスト |
| `formulas` | `dict[str, dict[tuple[int, int], str]]` | シート名→(行, 列)→数式文字列 |
| `encoding` | `str \| None` | ファイルの文字エンコーディング |
| `sheet_index` | `int` | 対象シートのインデックス。デフォルト: `0`（`create_context` のみ） |
| `config` | `Config \| None` | 設定オーバーライド（`create_context` のみ） |
| `column_schemas` | `list[ColumnSchema] \| None` | カラムスキーマのオーバーライド（`create_context` のみ） |
| `stub_cols` | `list[int] \| None` | 行ヘッダー列番号のオーバーライド（`create_context` のみ） |

## 新しいルールのテスト追加手順

1. テストディレクトリを作成:
   ```bash
   mkdir -p tests/rules/L{N}_{NN}_{rule_name}
   touch tests/rules/L{N}_{NN}_{rule_name}/__init__.py
   ```

2. `test_check.py` を作成:
   ```python
   from harunobu.rules.level{N}.L{N}_{NN}_{rule_name} import SomeRule

   class TestSomeRule:
       def test_pass_case(self, create_context):
           """合格ケース"""
           context = create_context(sheets_data={"Sheet1": [["ID", "値"], [1, 100]]})
           result = SomeRule().check(context)
           assert result.passed
           assert result.score == 100

       def test_violation_case(self, create_context):
           """違反ケース"""
           context = create_context(sheets_data={"Sheet1": [["ID", "値"], [1, "100円"]]})
           result = SomeRule().check(context)
           assert not result.passed
           assert len(result.violations) > 0
   ```

3. テストを実行:
   ```bash
   uv run pytest tests/rules/L{N}_{NN}_{rule_name}/ -v
   ```

## コード品質

- 命名規約: snake_case（変数・関数）、PascalCase（クラス）、定数は UPPER_SNAKE_CASE
- 型ヒント: すべての関数シグネチャに型アノテーションを付与（Python 3.10+ 互換の記法）
- テスト命名: `test_` プレフィックス + 検証内容を端的に表現（例: `test_no_merged_cells`, `test_single_merge_in_header`）
- テストクラス: 同一ルールのテストは `TestRuleName` クラスにまとめる
- 1テスト1観点: 各テスト関数は1つの振る舞いのみを検証する
