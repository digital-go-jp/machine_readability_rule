"""L2-01 用サンプル（数値データの純粋性）。

OK:   年月・売上・費用・利益がすべて数値の月次損益表。
NG-01: 利益列の負値を ▲記号で表記（▲50,000）。
NG-02: 費用列に「円」単位を付与（350000円）。
NG-03: 売上列に ¥記号（¥400,000）+ 利益列の負値を括弧表記（(50000)）。
NG-04: 利益列の数値をスペース区切り（150 000）+ 負値を ▲スペース区切り（▲50 000）。
NG-05: 利益列の一部に脚注記号付き表記（0(a）+ 表下に注釈行。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .common import make_empty_workbook, save_workbook

_HEADER = ["年月", "売上", "費用", "利益"]
_MONTHS = [date(2025, m, 1) for m in [1, 2, 3, 4, 5]]
_SALES = [500000, 400000, 300000, 300000, 500000]
_COSTS = [350000, 350000, 350000, 350000, 350000]
_PROFITS = [150000, 50000, -50000, -50000, 150000]


def _write_header(ws) -> None:
    for col, h in enumerate(_HEADER, start=1):
        ws.cell(row=1, column=col, value=h)


def _write_ok(ws) -> None:
    _write_header(ws)
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=cost)
        ws.cell(row=i, column=4, value=profit)


def _write_ng01(ws) -> None:
    """利益の負値を ▲記号文字列で表記。"""
    _write_header(ws)
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=cost)
        profit_val = f"▲{-profit:,}" if profit < 0 else profit
        ws.cell(row=i, column=4, value=profit_val)


def _write_ng02(ws) -> None:
    """費用列に「円」単位を付与。"""
    _write_header(ws)
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=f"{cost}円" if i >= 4 else cost)
        ws.cell(row=i, column=4, value=profit)


def _write_ng03(ws) -> None:
    """売上に ¥記号 + 利益の負値を括弧表記。"""
    _write_header(ws)
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        sale_val = f"¥{sale:,}" if i in (3, 4, 5) else sale
        ws.cell(row=i, column=2, value=sale_val)
        ws.cell(row=i, column=3, value=cost)
        profit_val = f"({-profit})" if profit < 0 else profit
        ws.cell(row=i, column=4, value=profit_val)


def _write_ng04(ws) -> None:
    """利益列をスペース区切り表記（▲50 000 / 150 000）。"""
    _write_header(ws)
    for i, (m, sale, cost, profit) in enumerate(zip(_MONTHS, _SALES, _COSTS, _PROFITS, strict=True), start=2):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=cost)
        if profit < 0:
            profit_val = f"▲{-profit:,}".replace(",", " ")
        else:
            profit_val = f"{profit:,}".replace(",", " ")
        ws.cell(row=i, column=4, value=profit_val)


def _write_ng05(ws) -> None:
    """利益列の一部に脚注記号付き表記 + 表下に注釈行。"""
    _write_header(ws)
    # 費用を調整して利益が 0 になる行（脚注を付ける対象）
    adjusted_costs = [350000, 350000, 300000, 300000, 350000]
    adjusted_profits = [150000, 50000, 0, 0, 150000]
    for i, (m, sale, cost, profit) in enumerate(
        zip(_MONTHS, _SALES, adjusted_costs, adjusted_profits, strict=True), start=2
    ):
        ws.cell(row=i, column=1, value=m)
        ws.cell(row=i, column=2, value=sale)
        ws.cell(row=i, column=3, value=cost)
        profit_val = "0(a" if profit == 0 else profit
        ws.cell(row=i, column=4, value=profit_val)
    # 注釈行
    note_row = len(_MONTHS) + 2
    ws.cell(row=note_row, column=1, value="※a")
    ws.cell(row=note_row, column=2, value="費用調整済み")


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet)

    for title, writer in [
        ("NG-01", _write_ng01),
        ("NG-02", _write_ng02),
        ("NG-03", _write_ng03),
        ("NG-04", _write_ng04),
        ("NG-05", _write_ng05),
    ]:
        _write_writer = writer
        ws = workbook.create_sheet(title)
        _write_writer(ws)

    return [save_workbook(output_dir, workbook, "rule_16_number_column")]
