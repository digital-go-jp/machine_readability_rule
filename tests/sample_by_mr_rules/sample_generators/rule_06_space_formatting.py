"""L1-06 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import (
    base_rows,
    make_empty_workbook,
    save_workbook,
    set_cell_value,
    write_base_data,
    write_delimited_file,
    write_rows,
)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    write_base_data(ok_sheet)

    ok_english = workbook.create_sheet("OK-EN")
    write_rows(ok_english, base_rows(english=True))
    ok_english.cell(row=1, column=7, value="Notes")
    ok_english.cell(row=2, column=7, value="Northern region")
    ok_english.cell(row=3, column=7, value="Population estimate")

    ng_sheet = workbook.create_sheet("NG-01")
    write_base_data(ng_sheet)
    ng_sheet.cell(row=2, column=1, value="  北海道")
    ng_sheet.cell(row=3, column=1, value="　青森県")
    ng_sheet.cell(row=5, column=1, value="宮城県  ")

    ng_middle_space = workbook.create_sheet("NG-02")
    write_base_data(ng_middle_space)
    ng_middle_space.cell(row=2, column=1, value="北  海道")
    ng_middle_space.cell(row=3, column=1, value="青  森県")
    ng_middle_space.cell(row=4, column=1, value="岩  手県")
    ng_middle_space.cell(row=1, column=3, value="2021  年")

    ng_linebreak = workbook.create_sheet("NG-03")
    write_base_data(ng_linebreak)
    set_cell_value(ng_linebreak, 2, 1, "北海道\n（道内）")
    set_cell_value(ng_linebreak, 3, 1, "青森県\n（東北）")
    set_cell_value(ng_linebreak, 1, 2, "2020年\n人口")
    set_cell_value(ng_linebreak, 1, 3, "2021年\n人口")

    workbook_path = save_workbook(output_dir, workbook, "rule_06_space_formatting")

    ok_csv_path = write_delimited_file(
        output_dir,
        "rule_06_space_formatting_OK.csv",
        base_rows(),
        delimiter=",",
        encoding="utf-8-sig",
    )
    ok_english_csv_path = write_delimited_file(
        output_dir,
        "rule_06_space_formatting_OK-English.csv",
        [
            ["Prefecture", "Notes", "Population"],
            ["Hokkaido Prefecture", "Northern region", 5250],
            ["Aomori Prefecture", "Population estimate", 1246],
        ],
        delimiter=",",
        encoding="utf-8-sig",
    )
    ng_csv_01_path = write_delimited_file(
        output_dir,
        "rule_06_space_formatting_NG-01.csv",
        [
            ["都道府県", "2020  年"],
            ["  北海道", 5250],
            ["青  森県", 1246],
        ],
        delimiter=",",
        encoding="utf-8-sig",
    )
    ng_csv_02_path = write_delimited_file(
        output_dir,
        "rule_06_space_formatting_NG-02.csv",
        [
            ["都道府県", "2020年\n人口"],
            ["北海道\n（道内）", 5250],
            ["青森県\n（東北）", 1246],
        ],
        delimiter=",",
        encoding="utf-8-sig",
    )

    return [workbook_path, ok_csv_path, ok_english_csv_path, ng_csv_01_path, ng_csv_02_path]
