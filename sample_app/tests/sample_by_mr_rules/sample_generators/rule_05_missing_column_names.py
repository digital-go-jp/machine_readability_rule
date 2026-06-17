"""L1-05 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook, write_base_data


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    write_base_data(ok_sheet)

    missing_header_sheet = workbook.create_sheet("NG-01")
    write_base_data(missing_header_sheet)
    # openpyxl は cell(..., value=None) を「未指定」扱いし既存値が残るため .value で消す
    missing_header_sheet.cell(row=1, column=3).value = None
    missing_header_sheet.cell(row=1, column=5).value = None

    serial_header_sheet = workbook.create_sheet("NG-02")
    write_base_data(serial_header_sheet)
    serial_header_sheet.cell(row=1, column=1, value="001")
    serial_header_sheet.cell(row=1, column=2, value="002")
    serial_header_sheet.cell(row=1, column=3, value="003")
    serial_header_sheet.cell(row=1, column=4, value="004")
    serial_header_sheet.cell(row=1, column=5, value="005")
    serial_header_sheet.cell(row=1, column=6, value="006")

    return [save_workbook(output_dir, workbook, "rule_05_missing_column_names")]
