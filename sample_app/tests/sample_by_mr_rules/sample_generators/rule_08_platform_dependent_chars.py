"""L1-08 用サンプル（機種依存文字）。

埋め込み文字は L1_08_platform_dependent_chars の検出と一致させる。
unicodedata.name は可読性のためのコメント用途（チェックロジックは重複させない）。
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from .common import make_empty_workbook, save_workbook, write_delimited_file, write_rows

# 丸数字 ① (CIRCLED DIGIT ONE) — unicodedata.name("\u2460") == "CIRCLED DIGIT ONE"
_CIRCLED_1 = "\u2460"
_CIRCLED_5 = "\u2464"
_CIRCLED_10 = "\u2469"

# ローマ数字 Ⅲ — unicodedata.name("\u2162") == "ROMAN NUMERAL THREE"
_ROMAN_3 = "\u2162"

# 機種依存記号（L1-08 テストと同系）
# ㈱ — unicodedata.name("\u3231") == "PARENTHESIZED IDEOGRAPH STOCK"
_PAREN_STOCK = "\u3231"
# ㍉ — unicodedata.name("\u3349") == "SQUARE MILI"
_SQUARE_MILI = "\u3349"

# 単位 ㎡ — L1-08 の COMMON_UNIT_SYMBOLS に含まれ警告にならない
# unicodedata.name("\u33a1") == "SQUARE METER"
_SQUARE_METER = "\u33a1"


def _assert_doc_names() -> None:
    """開発時に文字とコメントの対応を壊していないか確認（import 時は no-op 相当の軽量チェック）。"""
    assert unicodedata.name(_CIRCLED_1).startswith("CIRCLED")
    assert "ROMAN" in unicodedata.name(_ROMAN_3)
    assert unicodedata.name(_PAREN_STOCK).startswith("PARENTHESIZED")


_assert_doc_names()


def _write_ok(ws) -> None:
    rows = [
        ["項目", "値", "備考"],
        ["東京都", 1000, "通常の日本語"],
        ["面積(参考)", 50, f"{_SQUARE_METER}のみは単位ホワイトリスト対象"],
        ["コード", "A-01", "半角英数"],
    ]
    write_rows(ws, rows)


def _write_ng_circled(ws) -> None:
    rows = [
        ["番号", "内容"],
        [_CIRCLED_1, "丸数字ラベル"],
        [_CIRCLED_5, "項目⑤相当"],
        [_CIRCLED_10, "10番台"],
    ]
    write_rows(ws, rows)


def _write_ng_roman(ws) -> None:
    rows = [
        ["章", "タイトル"],
        [_ROMAN_3, "概要"],
        ["Ⅳ", "詳細"],  # \u2163
    ]
    write_rows(ws, rows)


def _write_ng_symbols(ws) -> None:
    rows = [
        ["会社名", "単位メモ"],
        [f"{_PAREN_STOCK}サンプル", _SQUARE_MILI],
        ["参照", "㌔㌢"],  # U+3354 U+3352 など _PLATFORM_DEPENDENT_RE 範囲
    ]
    write_rows(ws, rows)


def _write_ok_roman_code(ws) -> None:
    """行政データの分類コード（Ⅰ-0 等）は L1-08 で info に降格し passed 維持。"""
    rows = [
        ["項目", "値"],
        ["Ⅰ-0", "data"],
        ["Ⅱ－１", "data"],  # 全角マイナス・全角数字もパターン内
        ["Ⅲ-2", "data"],
    ]
    write_rows(ws, rows)


# CSV 用: 丸数字・ローマ数字・機種依存記号を 1ファイルにまとめた行
_CSV_ROWS_WITH_PLATFORM_CHARS = [
    ["番号", "章", "会社名", "単位メモ"],
    [_CIRCLED_1, _ROMAN_3, f"{_PAREN_STOCK}サンプル", _SQUARE_MILI],
    [_CIRCLED_5, "Ⅳ", "参照", "㌔㌢"],
    [_CIRCLED_10, "Ⅴ", "通常会社", "通常メモ"],
]


def generate(output_dir: Path) -> list[Path]:
    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet)

    ng1 = workbook.create_sheet("NG-01")
    _write_ng_circled(ng1)

    ng2 = workbook.create_sheet("NG-02")
    _write_ng_roman(ng2)

    ng3 = workbook.create_sheet("NG-03")
    _write_ng_symbols(ng3)

    ok_code = workbook.create_sheet("OK-分類コード")
    _write_ok_roman_code(ok_code)

    xlsx_path = save_workbook(output_dir, workbook, "rule_08_platform_dependent_chars")

    # Shift-JIS(CP932) で読み込まれた場合のみ NG とするため、同じ内容を 2 エンコーディングで出力する。
    ng_cp932_path = write_delimited_file(
        output_dir,
        "rule_08_platform_dependent_chars_NG-CP932.csv",
        _CSV_ROWS_WITH_PLATFORM_CHARS,
        delimiter=",",
        encoding="cp932",
    )
    ok_utf8_path = write_delimited_file(
        output_dir,
        "rule_08_platform_dependent_chars_OK-UTF8.csv",
        _CSV_ROWS_WITH_PLATFORM_CHARS,
        delimiter=",",
        encoding="utf-8-sig",
    )

    return [xlsx_path, ng_cp932_path, ok_utf8_path]
