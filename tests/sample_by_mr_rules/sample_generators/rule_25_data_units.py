"""L3-04 用サンプル（データの単位を記載しているか）。

OK:         数値列ヘッダーに括弧付きで単位を明記。
OK-Implied: 単位を暗示する語（金額・人口・年齢）のみで括弧表記なし。
NG-01:      数値列ヘッダーに単位がなく暗示語にも該当しない（全列違反）。
NG-02:      一部の列だけ単位欠落（混在）。
"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook

_ROWS_OK: list[tuple[str, int, int, int]] = [
    ("A市", 1200000, 100, 350),
    ("B市", 980000, 80, 410),
    ("C市", 2100000, 150, 290),
    ("D市", 760000, 60, 510),
]

_ROWS_OK_IMPLIED: list[tuple[str, int, int, int]] = [
    ("商品A", 1500, 250000, 25),
    ("商品B", 3200, 510000, 38),
    ("商品C", 880, 90000, 47),
    ("商品D", 12000, 1800000, 33),
]

_ROWS_NG01: list[tuple[str, float, float, float]] = [
    ("X", 12.4, 88.0, 3.5),
    ("Y", 18.9, 73.5, 4.1),
    ("Z", 25.0, 92.1, 5.7),
    ("W", 9.6, 64.2, 2.9),
]

_ROWS_NG02: list[tuple[str, int, int, int]] = [
    ("北エリア", 1500, 80, 12),
    ("南エリア", 2200, 110, 18),
    ("東エリア", 1800, 95, 15),
    ("西エリア", 3000, 130, 22),
]


def _write_ok(ws) -> None:
    """全数値列に括弧付きの単位を明記。"""
    ws.cell(row=1, column=1, value="地域名")
    ws.cell(row=1, column=2, value="売上（円）")
    ws.cell(row=1, column=3, value="数量（個）")
    ws.cell(row=1, column=4, value="面積（㎡）")
    for i, (name, sales, qty, area) in enumerate(_ROWS_OK, start=2):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=sales)
        ws.cell(row=i, column=3, value=qty)
        ws.cell(row=i, column=4, value=area)


def _write_ok_implied(ws) -> None:
    """括弧表記はないが、暗示的に単位が明らかなヘッダー名。"""
    ws.cell(row=1, column=1, value="商品名")
    ws.cell(row=1, column=2, value="人口")
    ws.cell(row=1, column=3, value="金額")
    ws.cell(row=1, column=4, value="年齢")
    for i, (name, pop, amt, age) in enumerate(_ROWS_OK_IMPLIED, start=2):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=pop)
        ws.cell(row=i, column=3, value=amt)
        ws.cell(row=i, column=4, value=age)


def _write_ng01(ws) -> None:
    """数値列のヘッダーが「数値1」「データ」「スコア」など単位不明。"""
    ws.cell(row=1, column=1, value="名前")
    ws.cell(row=1, column=2, value="数値1")
    ws.cell(row=1, column=3, value="データ")
    ws.cell(row=1, column=4, value="スコア")
    for i, (name, v1, v2, v3) in enumerate(_ROWS_NG01, start=2):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=v1)
        ws.cell(row=i, column=3, value=v2)
        ws.cell(row=i, column=4, value=v3)


def _write_ng02(ws) -> None:
    """1 列だけ単位欠落（「売上（円）」はOK・「数量」は欠落・「面積（㎡）」はOK）。"""
    ws.cell(row=1, column=1, value="エリア")
    ws.cell(row=1, column=2, value="売上（円）")
    ws.cell(row=1, column=3, value="数量")
    ws.cell(row=1, column=4, value="面積（㎡）")
    for i, (name, sales, qty, area) in enumerate(_ROWS_NG02, start=2):
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=sales)
        ws.cell(row=i, column=3, value=qty)
        ws.cell(row=i, column=4, value=area)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet)

    for title, writer in [
        ("OK-Implied", _write_ok_implied),
        ("NG-01", _write_ng01),
        ("NG-02", _write_ng02),
    ]:
        ws = workbook.create_sheet(title)
        writer(ws)

    return [save_workbook(output_dir, workbook, "rule_25_data_units")]
