"""L1-03 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook, write_base_data


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    write_base_data(ok_sheet)

    ng_vertical = workbook.create_sheet("NG-01")
    ng_vertical.cell(row=1, column=1, value="")
    ng_vertical.cell(row=2, column=1, value="")
    write_base_data(ng_vertical, start_row=3)
    ng_vertical.insert_rows(6)

    ng_horizontal = workbook.create_sheet("NG-02")
    write_base_data(ng_horizontal)
    ng_horizontal.insert_cols(4)

    return [save_workbook(output_dir, workbook, "rule_03_fragmented_data")]
