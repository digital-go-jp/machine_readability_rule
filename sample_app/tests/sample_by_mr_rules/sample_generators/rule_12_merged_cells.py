"""L1-12 用サンプル（セル結合）。

OK: 結合なしの人口表。
NG-01: ヘッダ行付近で年度列を横方向に結合したタイトル行を置く例。
NG-02: データ列で同一ラベルを縦方向に結合した例。
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from .common import POP_DATA, PREFECTURES, YEARS, write_base_data


def _write_ok(ws) -> None:
    write_base_data(ws)


def _write_ng01(ws) -> None:
    """1 行目にデータ列上の横結合（ヘッダ領域の結合に相当）。"""
    ws.merge_cells("B1:F1")
    ws.cell(row=1, column=1, value="都道府県")
    ws.cell(row=1, column=2, value="人口推移（各年・千人）")
    header_row = 2
    ws.cell(row=header_row, column=1, value="都道府県")
    for index, year in enumerate(YEARS, start=2):
        ws.cell(row=header_row, column=index, value=f"{year}年")
    for pref_index, prefecture in enumerate(PREFECTURES, start=header_row + 1):
        ws.cell(row=pref_index, column=1, value=prefecture)
        for value_index, value in enumerate(POP_DATA[pref_index - header_row - 1], start=2):
            ws.cell(row=pref_index, column=value_index, value=value)


def _write_ng02(ws) -> None:
    """データ領域で都道府県列を縦結合（例: 先頭 2 行を 1 ラベルにまとめる）。"""
    write_base_data(ws)
    # 既定レイアウト: 1 行目ヘッダ、2-6 行がデータ。A3:A4（青森・岩手）を結合
    ws.merge_cells("A3:A4")
    ws.cell(row=3, column=1, value="東北（青森・岩手）")
    ws.cell(row=4, column=1, value=None)


def generate(output_dir: Path) -> list[Path]:
    path = output_dir / "rule_12_merged_cells.xlsx"
    wb = Workbook()

    ws_ok = wb.active
    ws_ok.title = "OK"
    _write_ok(ws_ok)

    ws_ng1 = wb.create_sheet("NG-01")
    _write_ng01(ws_ng1)

    ws_ng2 = wb.create_sheet("NG-02")
    _write_ng02(ws_ng2)

    wb.save(path)
    return [path]
