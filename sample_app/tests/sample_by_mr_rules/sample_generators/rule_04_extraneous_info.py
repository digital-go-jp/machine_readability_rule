"""L1-04 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook, write_base_data


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    write_base_data(ok_sheet)

    ng_sheet = workbook.create_sheet("NG-01")
    write_base_data(ng_sheet)
    ng_sheet.cell(row=1, column=9, value="※このデータは暫定値です")
    ng_sheet.cell(row=8, column=1, value="出典：総務省統計局")
    ng_sheet.cell(row=9, column=1, value="作成者：山田太郎")
    ng_sheet.cell(row=10, column=1, value="最終更新：2024/3/15")

    adjacent_sheet = workbook.create_sheet("NG-02")
    write_base_data(adjacent_sheet)
    adjacent_sheet.cell(row=2, column=7, value="暫定値を含む")
    adjacent_sheet.cell(row=3, column=7, value="担当: 政策企画課")
    adjacent_sheet.cell(row=7, column=1, value="出典: 総務省統計局")

    return [save_workbook(output_dir, workbook, "rule_04_extraneous_info")]
