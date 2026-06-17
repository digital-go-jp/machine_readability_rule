"""L2-06 用サンプル（数式を使用している場合は数値データに修正しているか）。

OK:   年月・売上・費用・利益がすべて静的な数値。
NG-01: 利益列に「=B{n}-C{n}」の四則演算数式が残存。
NG-02: 年月列に TEXT 数式（=TEXT(DATE(A{n},B{n},1),"YY年MM月")）が残存。
NG-03: 設問1回答列に VLOOKUP 数式が残存（コード表を別シートで参照）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .common import make_empty_workbook, save_workbook

_MONTHS = [date(2025, m, 1) for m in [1, 2, 3, 4, 5]]
_SALES = [500000, 400000, 300000, 300000, 500000]
_COSTS = [350000, 350000, 350000, 350000, 350000]
_PROFITS = [150000, 50000, -50000, -50000, 150000]

# NG-03: 設問コードデータ（15行分）
_SURVEY_CODES = [1, 1, 4, 1, 1, 3, 1, 2, 1, 4, 2, 3, 3, 4, 3]
_CODE_TABLE = [(1, "取組済"), (2, "取組予定"), (3, "未定"), (4, "その他")]


def _write_ok(ws) -> None:
    ws.cell(row=1, column=1, value="年月")
    ws.cell(row=1, column=2, value="売上")
    ws.cell(row=1, column=3, value="費用")
    ws.cell(row=1, column=4, value="利益")
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=cost)
        ws.cell(row=i, column=4, value=profit)


def _write_ng01(ws) -> None:
    """利益列が =B{n}-C{n} の数式（売上−費用）。"""
    ws.cell(row=1, column=1, value="年月")
    ws.cell(row=1, column=2, value="売上")
    ws.cell(row=1, column=3, value="費用")
    ws.cell(row=1, column=4, value="利益")
    for i, (m, sale, cost) in enumerate(zip(_MONTHS, _SALES, _COSTS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=cost)
        ws.cell(row=i, column=4, value=f"=B{i}-C{i}")


def _write_ng02(ws) -> None:
    """年月列が TEXT 数式（年・月の数値セルを文字列に変換）。"""
    ws.cell(row=1, column=1, value="年")
    ws.cell(row=1, column=2, value="月")
    ws.cell(row=1, column=3, value="年月")
    ws.cell(row=1, column=4, value="売上")
    ws.cell(row=1, column=5, value="費用")
    ws.cell(row=1, column=6, value="利益")
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m.year)
        ws.cell(row=i, column=2, value=m.month)
        ws.cell(row=i, column=3, value=f'=TEXT(DATE(A{i},B{i},1),"YY年MM月")')
        ws.cell(row=i, column=4, value=sale)
        ws.cell(row=i, column=5, value=cost)
        ws.cell(row=i, column=6, value=profit)


def _write_ng03(ws) -> None:
    """設問1回答列が VLOOKUP 数式（別シートのコード表を参照）。"""
    ws.cell(row=1, column=1, value="No")
    ws.cell(row=1, column=2, value="設問1コード")
    ws.cell(row=1, column=3, value="設問1回答")
    for i, code in enumerate(_SURVEY_CODES, start=2):
        ws.cell(row=i, column=1, value=i - 1)
        ws.cell(row=i, column=2, value=code)
        ws.cell(row=i, column=3, value=f"=VLOOKUP(B{i},'NG-03_コード'!$A:$B,2,FALSE)")


def _write_ng03_code_table(ws) -> None:
    """VLOOKUP 参照先のコード表シート。"""
    ws.cell(row=1, column=1, value="コード")
    ws.cell(row=1, column=2, value="設問1回答")
    for i, (code, label) in enumerate(_CODE_TABLE, start=2):
        ws.cell(row=i, column=1, value=code)
        ws.cell(row=i, column=2, value=label)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet)

    ws_ng01 = workbook.create_sheet("NG-01")
    _write_ng01(ws_ng01)

    ws_ng02 = workbook.create_sheet("NG-02")
    _write_ng02(ws_ng02)

    ws_ng03 = workbook.create_sheet("NG-03")
    _write_ng03(ws_ng03)

    ws_ng03_code = workbook.create_sheet("NG-03_コード")
    _write_ng03_code_table(ws_ng03_code)

    return [save_workbook(output_dir, workbook, "rule_21_formula_convert_integer")]
