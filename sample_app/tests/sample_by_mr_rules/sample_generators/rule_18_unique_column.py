"""L2-03 用サンプル（各列が一意に識別可能な項目名を持っているか）。

OK:   「財務情報 売上高」「財務情報 営業利益」と連結した一意な列名を持つ表。
NG-01: 1行目に「財務情報」が結合（同名の親ヘッダー）、2行目に「売上高」「営業利益」—
       各列が単独では「売上高」「営業利益」と同名になりうる多段ヘッダー。
NG-02: 1行目が空欄（会社列なし）、2行目に単位行（「千円」重複）—
       列名が確定できない構造。
NG-03: 単一行ヘッダーで横結合あり（カテゴリ列）— L2 では結合ヘッダー自体を許容しない。
NG-04: 親行に複数のグループ横結合（複数のマルチヘッダー＆セル結合）— 各従属セルが違反。
"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook

_COMPANY_DATA: list[tuple[str, int, int]] = [
    ("A", 120000, 15000),
    ("B", 130000, 15000),
    ("C", 125000, 15000),
]


def _write_ok(ws) -> None:
    ws.cell(row=1, column=1, value="会社")
    ws.cell(row=1, column=2, value="財務情報 売上高")
    ws.cell(row=1, column=3, value="財務情報 営業利益")
    for i, (company, sales, profit) in enumerate(_COMPANY_DATA, start=2):
        ws.cell(row=i, column=1, value=company)
        ws.cell(row=i, column=2, value=sales)
        ws.cell(row=i, column=3, value=profit)


def _write_ng01(ws) -> None:
    """親ヘッダー「財務情報」が2列にまたがり重複する多段ヘッダー。"""
    # 1行目: 「財務情報」が B-C 列にまたがる（結合相当）
    ws.merge_cells("B1:C1")
    ws.cell(row=1, column=1, value=None)
    ws.cell(row=1, column=2, value="財務情報")
    # 2行目: 実際の列名
    ws.cell(row=2, column=1, value="会社")
    ws.cell(row=2, column=2, value="売上高")
    ws.cell(row=2, column=3, value="営業利益")
    for i, (company, sales, profit) in enumerate(_COMPANY_DATA, start=3):
        ws.cell(row=i, column=1, value=company)
        ws.cell(row=i, column=2, value=sales)
        ws.cell(row=i, column=3, value=profit)


def _write_ng02(ws) -> None:
    """1行目が空欄（会社列なし）、2行目が単位行で列名未確定。"""
    # 1行目: 会社列ヘッダーがない
    ws.cell(row=1, column=1, value=None)
    ws.cell(row=1, column=2, value="売上高")
    ws.cell(row=1, column=3, value="営業利益")
    # 2行目: 単位行（列名と混在）
    ws.cell(row=2, column=1, value="会社")
    ws.cell(row=2, column=2, value="千円")
    ws.cell(row=2, column=3, value="千円")
    for i, (company, sales, profit) in enumerate(_COMPANY_DATA, start=3):
        ws.cell(row=i, column=1, value=company)
        ws.cell(row=i, column=2, value=sales)
        ws.cell(row=i, column=3, value=profit)


def _write_ng03(ws) -> None:
    """単一行ヘッダーで横結合あり（カテゴリ列）。

    L1-12 ではヘッダー結合は許容（info）だが、
    L2-03 では結合ヘッダー自体を許容しない（除外パターンなし）。
    """
    # 1行目: A1:B1 を横結合（カテゴリ列を結合）
    ws.merge_cells("A1:B1")
    ws.cell(row=1, column=1, value="カテゴリ")
    ws.cell(row=1, column=3, value="値")
    for i, (company, sales, profit) in enumerate(_COMPANY_DATA, start=2):
        ws.cell(row=i, column=1, value=company)
        ws.cell(row=i, column=2, value=sales)
        ws.cell(row=i, column=3, value=profit)


def _write_ng04(ws) -> None:
    """親行に複数の横結合グループ（複数のマルチヘッダー＆セル結合）。

    親行 (Row1) に 2 つの結合グループ: B1:C1 と D1:E1。
    複数の結合の従属セルがそれぞれ違反として検出される。
    """
    # 親行: B1:C1（売上）と D1:E1（経費）を結合
    ws.merge_cells("B1:C1")
    ws.merge_cells("D1:E1")
    ws.cell(row=1, column=1, value=None)
    ws.cell(row=1, column=2, value="売上")
    ws.cell(row=1, column=4, value="経費")
    # 子行: 各列の詳細
    ws.cell(row=2, column=1, value="会社")
    ws.cell(row=2, column=2, value="国内")
    ws.cell(row=2, column=3, value="海外")
    ws.cell(row=2, column=4, value="国内")
    ws.cell(row=2, column=5, value="海外")
    # データ行
    for i, (company, _sales, _profit) in enumerate(_COMPANY_DATA, start=3):
        ws.cell(row=i, column=1, value=company)
        ws.cell(row=i, column=2, value=100)
        ws.cell(row=i, column=3, value=50)
        ws.cell(row=i, column=4, value=30)
        ws.cell(row=i, column=5, value=20)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet)

    for title, writer in [
        ("NG-01", _write_ng01),
        ("NG-02", _write_ng02),
        ("NG-03", _write_ng03),
        ("NG-04", _write_ng04),
    ]:
        ws = workbook.create_sheet(title)
        writer(ws)

    return [save_workbook(output_dir, workbook, "rule_18_unique_column")]
