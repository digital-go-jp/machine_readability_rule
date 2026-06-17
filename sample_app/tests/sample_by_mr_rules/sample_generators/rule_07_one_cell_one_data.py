"""L1-07 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook, set_cell_value


def _write_ok_sheet(ws) -> None:
    ws.cell(row=1, column=1, value="区分")
    ws.cell(row=1, column=2, value="企業等数")
    ws.cell(row=1, column=3, value="売上金額（百万円）")
    ws.cell(row=1, column=4, value="費用総額（百万円）")

    rows = [
        ("総計", 1188389, 391445, 355943),
        ("A", 50384, 69565, 63683),
        ("B", 154138, 50468, 45332),
        ("C", 86522, 44098, 33210),
        ("D", 85983, 22258, 20237),
        ("E", 580003, 37652, 35016),
        ("F", 27456, 15288, 14633),
        ("G", 119085, 115499, 110735),
        ("H", 84818, 36617, 32897),
    ]
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row=row_index, column=column_index, value=value)


def _write_ng_01(ws) -> None:
    ws.cell(row=1, column=1, value="区分")
    ws.cell(row=1, column=2, value="企業等数, 売上金額（費用総額）")

    rows = [
        ("総計", "1188389, 391445（355943）"),
        ("A", "50384, 69565（63683）"),
        ("B", "154138, 50468（45332）"),
        ("C", "86522, 44098（33210）"),
        ("D", "85983, 22258（20237）"),
        ("E", "580003, 37652（35016）"),
        ("F", "27456, 15288（14633）"),
        ("G", "119085, 115499（110735）"),
        ("H", "84818, 36617（32897）"),
    ]
    for row_index, (label, value) in enumerate(rows, start=2):
        ws.cell(row=row_index, column=1, value=label)
        ws.cell(row=row_index, column=2, value=value)


def _write_ng_02(ws) -> None:
    ws.cell(row=1, column=1, value="区分")
    ws.cell(row=1, column=2, value="企業等数")
    ws.cell(row=1, column=3, value="売上金額（費用総額）")

    rows = [
        ("総計", 1188389, "391445（355943）"),
        ("A", 50384, "69565（63683）"),
        ("B", 154138, "50468（45332）"),
        ("C", 86522, "44098（33210）"),
        ("D", 85983, "22258（20237）"),
        ("E", 580003, "37652（35016）"),
        ("F", 27456, "15288（14633）"),
        ("G", 119085, "115499（110735）"),
        ("H", 84818, "36617（32897）"),
    ]
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row=row_index, column=column_index, value=value)


def _write_ng_03(ws) -> None:
    ws.cell(row=1, column=1, value="項目")
    ws.cell(row=1, column=2, value="全国")

    ws.cell(row=2, column=1, value="仕入額")
    ws.cell(row=3, column=1, value="出荷額")

    set_cell_value(
        ws,
        2,
        2,
        "373（平成27年度）、434（平成28年度）、549（平成29年度）、638（平成30年度）、741（平成31年度）",
    )
    set_cell_value(
        ws,
        3,
        2,
        "973（平成27年度）、1234（平成28年度）、1449（平成29年度）、1738（平成30年度）、1841（平成31年度）",
    )


def _write_ng_04(ws) -> None:
    set_cell_value(ws, 1, 1, "商品\n月")
    ws.cell(row=1, column=2, value="商品A")
    ws.cell(row=1, column=3, value="商品B")
    ws.cell(row=1, column=4, value="商品C")

    rows = [
        ("1月", 84, 11, 92),
        ("2月", 82, 90, 42),
        ("3月", 27, 92, 51),
    ]
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row=row_index, column=column_index, value=value)


def _write_ng_05(ws) -> None:
    ws.cell(row=1, column=1, value="自治体")
    ws.cell(row=1, column=2, value="対応チャネル")
    ws.cell(row=1, column=3, value="備考")

    rows = [
        ("A市", "窓口・電話・メール", "代表的な受付手段"),
        ("B町", "電話・FAX", "高齢者向け"),
        ("C村", "窓口・オンライン", "予約制"),
    ]
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row=row_index, column=column_index, value=value)


def _write_ng_06(ws) -> None:
    ws.cell(row=1, column=1, value="自治体")
    ws.cell(row=1, column=2, value="対象年度")
    ws.cell(row=1, column=3, value="担当部門")

    rows = [
        ("A市", "2022年度\n2023年度", "企画課"),
        ("B町", "2021年度\n2022年度", "総務課"),
        ("C村", "2023年度\n2024年度", "政策推進課"),
    ]
    for row_index, row in enumerate(rows, start=2):
        ws.cell(row=row_index, column=1, value=row[0])
        set_cell_value(ws, row_index, 2, row[1])
        ws.cell(row=row_index, column=3, value=row[2])


def _write_ng_07(ws) -> None:
    ws.cell(row=1, column=1, value="自治体")
    ws.cell(row=1, column=2, value="関係部署")
    ws.cell(row=1, column=3, value="公開区分")

    rows = [
        ("A市", "総務課, 企画課, 財政課", "公開"),
        ("B町", "福祉課, 税務課", "限定公開"),
        ("C村", "農政課, 建設課, 観光課", "公開"),
    ]
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            ws.cell(row=row_index, column=column_index, value=value)


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok_sheet(ok_sheet)

    ng_sheet_01 = workbook.create_sheet("NG-01")
    _write_ng_01(ng_sheet_01)

    ng_sheet_02 = workbook.create_sheet("NG-02")
    _write_ng_02(ng_sheet_02)

    ng_sheet_03 = workbook.create_sheet("NG-03")
    _write_ng_03(ng_sheet_03)

    ng_sheet_04 = workbook.create_sheet("NG-04")
    _write_ng_04(ng_sheet_04)

    ng_sheet_05 = workbook.create_sheet("NG-05")
    _write_ng_05(ng_sheet_05)

    ng_sheet_06 = workbook.create_sheet("NG-06")
    _write_ng_06(ng_sheet_06)

    ng_sheet_07 = workbook.create_sheet("NG-07")
    _write_ng_07(ng_sheet_07)

    return [save_workbook(output_dir, workbook, "rule_07_one_cell_one_data")]
