"""L2-02 用サンプル（データ内での項目名等の省略をしていないか）。

OK:   都道府県・市区町村・人口が全行に記載された表。
NG-01: 都道府県列を最初の市区のみ記載し、残りを空白で省略。
NG-02: 薬剤名列を先頭のみ記載し、残りを行番号（整数）で省略。
NG-03: 薬剤名列を先頭のみ記載し、残りを〃で省略。
NG-04: 薬剤名列を先頭のみ記載し、残りを同上で省略。
"""

from __future__ import annotations

from pathlib import Path

from .common import make_empty_workbook, save_workbook

_CITY_POPULATION: list[tuple[str, str, int]] = [
    ("北海道", "札幌市", 1955678),
    ("北海道", "函館市", 236515),
    ("北海道", "小樽市", 104432),
    ("北海道", "旭川市", 316183),
    ("北海道", "釧路市", 154271),
    ("北海道", "帯広市", 160810),
    ("北海道", "北見市", 110046),
    ("北海道", "苫小牧市", 165590),
    ("北海道", "江別市", 118055),
    ("青森県", "青森市", 263512),
    ("青森県", "弘前市", 159488),
    ("青森県", "八戸市", 215080),
    ("岩手県", "盛岡市", 277423),
    ("岩手県", "一関市", 105505),
    ("岩手県", "奥州市", 107798),
    ("宮城県", "仙台市", 1064142),
    ("宮城県", "石巻市", 132447),
    ("宮城県", "大崎市", 122035),
    ("秋田県", "秋田市", 293729),
    ("山形県", "山形市", 236164),
    ("山形県", "鶴岡市", 116731),
    ("福島県", "福島市", 264652),
    ("福島県", "会津若松市", 110841),
    ("福島県", "郡山市", 312433),
    ("福島県", "いわき市", 303171),
    ("茨城県", "水戸市", 267467),
    ("茨城県", "日立市", 163855),
    ("茨城県", "土浦市", 141571),
    ("茨城県", "古河市", 139812),
    ("茨城県", "取手市", 105872),
]

_DRUG_DATA: list[tuple[str, int]] = [
    ("鎮痛剤A-1", 429),
    ("鎮痛剤A-2", 321),
    ("鎮痛剤A-3", 384),
    ("鎮痛剤A-4", 408),
]


def _write_ok(ws) -> None:
    ws.cell(row=1, column=1, value="都道府県")
    ws.cell(row=1, column=2, value="市区町村")
    ws.cell(row=1, column=3, value="人口")
    for i, (pref, city, pop) in enumerate(_CITY_POPULATION, start=2):
        ws.cell(row=i, column=1, value=pref)
        ws.cell(row=i, column=2, value=city)
        ws.cell(row=i, column=3, value=pop)


def _write_ng01(ws) -> None:
    """都道府県列を先頭市区のみ記載し、残りを空白で省略。"""
    ws.cell(row=1, column=1, value="都道府県")
    ws.cell(row=1, column=2, value="市区町村")
    ws.cell(row=1, column=3, value="人口")

    prev_pref = None
    for i, (pref, city, pop) in enumerate(_CITY_POPULATION, start=2):
        pref_val = pref if pref != prev_pref else None
        ws.cell(row=i, column=1, value=pref_val)
        ws.cell(row=i, column=2, value=city)
        ws.cell(row=i, column=3, value=pop)
        prev_pref = pref


def _write_ng02(ws) -> None:
    """薬剤名列を行番号（整数）で省略。"""
    ws.cell(row=1, column=1, value="薬剤名")
    ws.cell(row=1, column=2, value="出荷本数")
    for i, (drug, count) in enumerate(_DRUG_DATA, start=2):
        drug_val = drug if i == 2 else i - 1  # 2→1は先頭、以降は行番号
        ws.cell(row=i, column=1, value=drug_val)
        ws.cell(row=i, column=2, value=count)


def _write_ng03(ws) -> None:
    """薬剤名列を〃（同上記号）で省略。"""
    ws.cell(row=1, column=1, value="薬剤名")
    ws.cell(row=1, column=2, value="出荷本数")
    for i, (drug, count) in enumerate(_DRUG_DATA, start=2):
        drug_val = drug if i == 2 else "〃"
        ws.cell(row=i, column=1, value=drug_val)
        ws.cell(row=i, column=2, value=count)


def _write_ng04(ws) -> None:
    """薬剤名列を「同上」テキストで省略。"""
    ws.cell(row=1, column=1, value="薬剤名")
    ws.cell(row=1, column=2, value="出荷本数")
    for i, (drug, count) in enumerate(_DRUG_DATA, start=2):
        drug_val = drug if i == 2 else "同上"
        ws.cell(row=i, column=1, value=drug_val)
        ws.cell(row=i, column=2, value=count)


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

    return [save_workbook(output_dir, workbook, "rule_17_omit_column")]
