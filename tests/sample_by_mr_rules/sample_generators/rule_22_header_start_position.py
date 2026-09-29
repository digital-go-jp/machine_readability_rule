"""L3-01 用サンプル（項目名行から始まり、次行からデータ入力がされているか）。

xlsx: 単一ファイル内に複数シートを配置。
  - OK: 1 行目ヘッダ、2 行目以降データ
  - NG-01: タイトル行を含み、ヘッダ位置が下にずれた構造（先頭行に内容残存）
  - NG-02: ヘッダ行とデータ行の間に空行が挟まる
  - NG-03: ヘッダーが 3 行にまたがる多段ヘッダー

csv:
  - OK: 1 行目ヘッダ、2 行目以降データ
  - NG-01: 先頭にタイトル行を含む（ヘッダが 3 行目）
"""

from __future__ import annotations

from pathlib import Path

from .common import (
    PREFECTURES,
    YEARS,
    make_empty_workbook,
    save_workbook,
    write_base_data,
    write_delimited_file,
)


def _write_multi_header(ws) -> None:
    """3 行多段ヘッダー + データ行を書く。"""
    ws.cell(row=1, column=1, value="地域")
    ws.cell(row=2, column=1, value="都道府県")
    ws.cell(row=3, column=1, value="名称")
    for index, year in enumerate(YEARS, start=2):
        ws.cell(row=1, column=index, value="人口")
        ws.cell(row=2, column=index, value=f"{year}年")
        ws.cell(row=3, column=index, value="千人")
    for pref_index, prefecture in enumerate(PREFECTURES, start=4):
        ws.cell(row=pref_index, column=1, value=prefecture)
        for col_index, year_index in enumerate(range(len(YEARS)), start=2):
            ws.cell(row=pref_index, column=col_index, value=1000 + pref_index + year_index)


def _write_with_blank_gap(ws) -> None:
    """ヘッダ行直後に空行を挟んでデータを書く。"""
    write_base_data(ws, start_row=1)
    # write_base_data はヘッダ + データを連続で書くので、行 2 をクリアして空行化し、
    # データを 1 行下にずらす。
    ws.insert_rows(2)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    write_base_data(ok_sheet)

    ng_title = workbook.create_sheet("NG-01")
    write_base_data(ng_title, title_row=True)

    ng_gap = workbook.create_sheet("NG-02")
    _write_with_blank_gap(ng_gap)

    ng_multi_header = workbook.create_sheet("NG-03")
    _write_multi_header(ng_multi_header)

    xlsx_path = save_workbook(output_dir, workbook, "rule_22_header_start_position")

    # CSV samples
    ok_csv_rows: list[list[object]] = [["都道府県", *[f"{year}年" for year in YEARS]]]
    for pref_index, prefecture in enumerate(PREFECTURES):
        ok_csv_rows.append([prefecture, *(2000 + pref_index + i for i in range(len(YEARS)))])
    ok_csv_path = write_delimited_file(
        output_dir,
        "rule_22_header_start_position_OK.csv",
        ok_csv_rows,
        delimiter=",",
        encoding="utf-8-sig",
    )

    ng_csv_rows: list[list[object]] = [
        ["都道府県別人口データ"],
        [""],
        ["都道府県", *[f"{year}年" for year in YEARS]],
    ]
    for pref_index, prefecture in enumerate(PREFECTURES):
        ng_csv_rows.append([prefecture, *(2000 + pref_index + i for i in range(len(YEARS)))])
    ng_csv_path = write_delimited_file(
        output_dir,
        "rule_22_header_start_position_NG-01.csv",
        ng_csv_rows,
        delimiter=",",
        encoding="utf-8-sig",
    )

    return [xlsx_path, ok_csv_path, ng_csv_path]
