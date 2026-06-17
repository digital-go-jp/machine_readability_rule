"""L2-05 用サンプル（選択肢列と「その他」の詳細記入が分離されているか）。

OK:   No・設問1・「設問1: その他の事由」が分離された表（50行）。
NG-01: 「その他」の詳細が選択肢列と同一セルに「4. その他: 〇〇」形式で混在。
NG-02: 選択肢値が先頭スペース付き（入力ミス）で、その他詳細も「 その他: 〇〇」と混在。
"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook

# OK シートのデータ: (No, 設問1, その他詳細 or None)
_OK_DATA: list[tuple[int, str, str | None]] = [
    (1, "1. 取組済", None),
    (2, "1. 取組済", None),
    (3, "4. その他", "対象となる事務を他団体に委託しているため"),
    (4, "1. 取組済", None),
    (5, "1. 取組済", None),
    (6, "3. 未定", None),
    (7, "1. 取組済", None),
    (8, "2. 取組予定", None),
    (9, "1. 取組済", None),
    (10, "4. その他", "外部団体による実施"),
    (11, "2. 取組予定", None),
    (12, "3. 未定", None),
    (13, "3. 未定", None),
    (14, "4. その他", "対象範囲の調査中のため"),
    (15, "3. 未定", None),
    (16, "2. 取組予定", None),
    (17, "2. 取組予定", None),
    (18, "3. 未定", None),
    (19, "2. 取組予定", None),
    (20, "1. 取組済", None),
    (21, "3. 未定", None),
    (22, "2. 取組予定", None),
    (23, "2. 取組予定", None),
    (24, "2. 取組予定", None),
    (25, "1. 取組済", None),
    (26, "4. その他", "R6.4.1時点で未定"),
    (27, "1. 取組済", None),
    (28, "3. 未定", None),
    (29, "3. 未定", None),
    (30, "4. その他", "取りまとめ中のため不明"),
    (31, "3. 未定", None),
    (32, "1. 取組済", None),
    (33, "3. 未定", None),
    (34, "3. 未定", None),
    (35, "3. 未定", None),
    (36, "2. 取組予定", None),
    (37, "1. 取組済", None),
    (38, "1. 取組済", None),
    (39, "1. 取組済", None),
    (40, "1. 取組済", None),
    (41, "2. 取組予定", None),
    (42, "1. 取組済", None),
    (43, "1. 取組済", None),
    (44, "1. 取組済", None),
    (45, "2. 取組予定", None),
    (46, "2. 取組予定", None),
    (47, "1. 取組済", None),
    (48, "4. その他", "わからん"),
    (49, "2. 取組予定", None),
    (50, "1. 取組済", None),
]

# NG-02 では row 26 の「その他」を「取組済」に変更（データ分布を変える）
_NG02_OVERRIDE: dict[int, str] = {26: "1. 取組済"}


def _write_ok(ws) -> None:
    ws.cell(row=1, column=1, value="No")
    ws.cell(row=1, column=2, value="設問1")
    ws.cell(row=1, column=3, value="設問1: その他の事由")
    for i, (no, choice, detail) in enumerate(_OK_DATA, start=2):
        ws.cell(row=i, column=1, value=no)
        ws.cell(row=i, column=2, value=choice)
        ws.cell(row=i, column=3, value=detail)


def _write_ng01(ws) -> None:
    """「その他」詳細を「4. その他: 〇〇」で同一セルに混在。"""
    ws.cell(row=1, column=1, value="No")
    ws.cell(row=1, column=2, value="設問1")
    for i, (no, choice, detail) in enumerate(_OK_DATA, start=2):
        ws.cell(row=i, column=1, value=no)
        if detail is not None:
            ws.cell(row=i, column=2, value=f"4. その他: {detail}")
        else:
            ws.cell(row=i, column=2, value=choice)


def _write_ng02(ws) -> None:
    """全選択肢値が先頭スペース付き + その他詳細を「 その他: 〇〇」で混在。"""
    ws.cell(row=1, column=1, value="No")
    ws.cell(row=1, column=2, value="設問1")
    for i, (no, choice, detail) in enumerate(_OK_DATA, start=2):
        ws.cell(row=i, column=1, value=no)
        # row 26 はその他ではなく取組済に差し替え
        override = _NG02_OVERRIDE.get(no)
        if override is not None:
            ws.cell(row=i, column=2, value=f" {override.lstrip('0123456789. ')}")
        elif detail is not None:
            ws.cell(row=i, column=2, value=f" その他: {detail}")
        else:
            # 「1. 取組済」→「 取組済」のように先頭スペース + 番号なし
            label = choice.split(". ", 1)[-1]
            ws.cell(row=i, column=2, value=f" {label}")


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet)

    for title, writer in [
        ("NG-01", _write_ng01),
        ("NG-02", _write_ng02),
    ]:
        ws = workbook.create_sheet(title)
        writer(ws)

    return [save_workbook(output_dir, workbook, "rule_20_split_other")]
