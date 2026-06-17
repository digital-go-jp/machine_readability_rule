"""L1-02 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import (
    PREFECTURES,
    YEARS,
    base_rows,
    make_empty_workbook,
    save_workbook,
    write_delimited_file,
    write_rows,
)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    write_rows(ok_sheet, base_rows())

    ng_sheet = workbook.create_sheet("NG-01")
    write_rows(ng_sheet, base_rows())

    start_row = 8
    ng_sheet.cell(row=start_row, column=1, value="面積（k㎡）")
    for column, year in enumerate(YEARS, start=2):
        ng_sheet.cell(row=start_row, column=column, value=f"{year}年")

    areas = [83424, 9646, 15275, 7282, 11638]
    for row_offset, (prefecture, area) in enumerate(zip(PREFECTURES, areas, strict=True), start=1):
        ng_sheet.cell(row=start_row + row_offset, column=1, value=prefecture)
        ng_sheet.cell(row=start_row + row_offset, column=2, value=area)

    workbook_path = save_workbook(output_dir, workbook, "rule_02_multiple_tables")

    ok_csv_path = write_delimited_file(
        output_dir,
        "rule_02_multiple_tables_OK.csv",
        base_rows(),
        delimiter=",",
        encoding="utf-8-sig",
    )

    ng_csv_rows = base_rows()
    ng_csv_rows.extend([[], ["面積（k㎡）", "値"]])
    ng_csv_rows.extend([[prefecture, area] for prefecture, area in zip(PREFECTURES, areas, strict=True)])
    ng_csv_path = write_delimited_file(
        output_dir,
        "rule_02_multiple_tables_NG-01.csv",
        ng_csv_rows,
        delimiter=",",
        encoding="utf-8-sig",
    )

    return [workbook_path, ok_csv_path, ng_csv_path]
