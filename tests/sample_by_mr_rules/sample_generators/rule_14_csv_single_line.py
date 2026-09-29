"""L1-14 用サンプル（CSV のデータ内改行）。

OK: NG-01 と同じ値だが、改行を含むフィールドをダブルクォートで囲んだ正しい CSV（1 レコード 1 物理行）。
NG-01: フィールド内の改行をダブルクォートで囲まずに書いた CSV
（1 レコードが複数物理行にまたがり、正しくパースできない）。
"""

from __future__ import annotations

from pathlib import Path

from .common import write_delimited_file, write_raw_text_file

# NG-01 と同じ論理データ（OK は csv.writer により改行フィールドがクォートされる）
_OK_AND_NG_ROWS = [
    ["都道府県", "備考"],
    ["北海道", "札幌市\n（道央）"],
    ["青森県", "県庁所在地\n青森市"],
]


def generate(output_dir: Path) -> list[Path]:
    ok_path = write_delimited_file(
        output_dir,
        "rule_14_csv_single_line_OK.csv",
        _OK_AND_NG_ROWS,
        delimiter=",",
        encoding="utf-8-sig",
    )

    # クォートなし: 「備考」列の値に改行があるが "..." で囲っていないため行が壊れる
    ng_content = "都道府県,備考\r\n北海道,札幌市\r\n（道央）\r\n青森県,県庁所在地\r\n青森市\r\n"
    ng_path = write_raw_text_file(
        output_dir,
        "rule_14_csv_single_line_NG-01.csv",
        ng_content,
        encoding="utf-8-sig",
    )

    return [ok_path, ng_path]
