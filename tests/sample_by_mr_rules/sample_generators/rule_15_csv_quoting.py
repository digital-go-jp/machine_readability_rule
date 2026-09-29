"""L1-15 用サンプル（CSV のクォーティング）。

OK: NG-01 と同じ値だが、カンマを含むフィールドをダブルクォートで囲んだ正しい CSV。
NG-01: カンマを含む値をダブルクォートで囲まずに書いた CSV（列数がずれる不正な形式）。
"""

from __future__ import annotations

from pathlib import Path

from .common import write_delimited_file, write_raw_text_file

# NG-01 と同じ論理データ（OK は csv.writer によりカンマを含むフィールドがクォートされる）
_OK_AND_NG_ROWS = [
    ["項目", "内容"],
    ["所在地", "東京都,港区"],
    ["摘要", "見積 1,200円（税込）"],
]


def generate(output_dir: Path) -> list[Path]:
    ok_path = write_delimited_file(
        output_dir,
        "rule_15_csv_quoting_OK.csv",
        _OK_AND_NG_ROWS,
        delimiter=",",
        encoding="utf-8-sig",
    )

    # クォートなし: 2 列想定だがカンマでフィールドが増えて見える
    ng_content = "項目,内容\r\n所在地,東京都,港区\r\n摘要,見積 1,200円（税込）\r\n"
    ng_path = write_raw_text_file(
        output_dir,
        "rule_15_csv_quoting_NG-01.csv",
        ng_content,
        encoding="utf-8-sig",
    )

    return [ok_path, ng_path]
