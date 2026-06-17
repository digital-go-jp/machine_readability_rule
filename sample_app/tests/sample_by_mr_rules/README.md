# テストデータ生成

## サンプルデータ生成

```bash
# pep723準拠のスクリプト pip install不要
# 登録済みルール番号のサンプルをすべて生成（番号は RULE_GENERATORS_BY_NUMBER を参照）
uv run generate_test_data.py

# 指定ルールだけ生成（他ルールの samples は削除・再生成しない）
uv run generate_test_data.py --rules 8
uv run generate_test_data.py -r 7,8
```

- `--rules` / `-r` を省略すると全ルール。指定時は **その番号の `rule_XX_*` だけ** を削除してから再生成する。

## データ生成スクリプト追加方法

1. `sample_app/tests/sample_by_mr_rules/sample_generators/` 配下に `rule_XX_xxx.py` を追加する
2. 各 module に `generate(output_dir: Path) -> list[Path]` を実装する
3. `sample_app/tests/sample_by_mr_rules/sample_generators/__init__.py` に import を追加し、`RULE_GENERATORS_BY_NUMBER` にルール番号をキーとして登録する（`RULE_GENERATORS` はこれから生成される）
4. 共通処理は `sample_app/tests/sample_by_mr_rules/sample_generators/common.py` に寄せる

最小例:

```python
from __future__ import annotations

from pathlib import Path


def generate(output_dir: Path) -> list[Path]:
    path = output_dir / "rule_99_example_OK.csv"
    path.write_text("col1,col2\n1,2\n", encoding="utf-8")
    return [path]
```

## 守ること

- `generate()` の返り値は、その module が新規生成したファイルの `Path` 一覧を返すこと
- 返り値に含める順序は、実際に生成・表示したい順にすること
- ファイル生成先は必ず `output_dir` 配下にすること
- 複数の NG 例を作る場合は `NG-01`, `NG-02` のように連番で命名すること
- OK 例は `..._OK.ext`、NG 例は `..._NG-01.ext` の形式にそろえること
- workbook を作る場合も csv/pdf/docx を作る場合も、最終的に生成されたファイルの `Path` を返すこと
- `generate_test_data.py` 側で、**実行対象の** rule の既存生成物（`rule_XX_` に一致するファイル）を消してから再生成するため、出力ファイル名は `rule_XX_` で始めること（全ルール実行時は全番号ぶん、 `--rules` 指定時はその番号ぶんのみ削除）
- 依存ライブラリを増やす場合は `sample_app/tests/sample_by_mr_rules/generate_test_data.py` 先頭の PEP 723 metadata も更新すること

## 補足

- 1つの `.xlsx` に `OK`, `NG-01`, `NG-02` など複数 sheet を入れてよい
- rule によっては `.xlsx` だけでなく `.csv`, `.pdf`, `.docx` を併せて生成してよい
