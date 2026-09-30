"""L1-10 用サンプル（Excel・埋め込みオブジェクトと表の位置関係）。

OK-01: テキストボックス + 表のみ（画像なし）。
OK-02: OK-01 と同一内容の表を A1 から配置し、オレンジ矩形を表の秋田県行付近（D 列）に配置。
NG-01: 表のみ A1 始まり。都道府県列（A）に塗りつぶしなしの正方形（枠線のみ PNG で代用）を 1 個だけ配置。
NG-02: 表は A1 始まり。「青森県」行だけ都道府県列（A3）を欠落させ数値（B3:C3）は残す。
その上に「青　森」テキストボックス（塗りなし・グレー枠）を置き、表のセル範囲とオブジェクトが重なる NG 例とする。

openpyxl はワークシート上のテキストボックスを生成できないため、本モジュールは XlsxWriter で書き出す。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import xlsxwriter
from PIL import Image as PILImage
from PIL import ImageDraw

# OK-01: テキストボックス下の表（1 行目ヘッダーの Excel 行番号）
_TABLE_START_ROW_OK = 6
# OK-02 / NG-01: 表は A1 から
_TABLE_START_ROW_OK02 = 1
_TABLE_START_ROW_NG = 1
# _table_rows() 先頭がヘッダー行。このインデックスの行だけ都道府県名列を書かない（NG-02）。
_MISSING_PREF_LABEL_ROW_OFFSET = 2


def _png_bytes_orange() -> bytes:
    buf = BytesIO()
    PILImage.new("RGB", (120, 90), color=(255, 140, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _png_bytes_square_outline(*, size: int = 26) -> bytes:
    """塗りつぶしなしの正方形（枠線のみ）。Excel 図形の代用。"""
    buf = BytesIO()
    im = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([0, 0, size - 1, size - 1], outline=(80, 80, 80), width=2)
    im.save(buf, format="PNG")
    return buf.getvalue()


def _table_rows() -> list[list[object]]:
    return [
        ["都道府県", "2023年", "2024年"],
        ["北海道", 5250, 5224],
        ["青森県", 1246, 1228],
        ["岩手県", 1227, 1211],
        ["宮城県", 2302, 2292],
        ["秋田県", 960, 941],
    ]


def _write_table_xlsx(
    worksheet: xlsxwriter.worksheet.Worksheet,
    workbook: xlsxwriter.Workbook,
    *,
    start_row_1based: int,
) -> None:
    """行番号は Excel の 1 始まり。"""
    header_fmt = workbook.add_format({"bold": True})
    base_row = start_row_1based - 1
    for r_off, row in enumerate(_table_rows()):
        for c_idx, value in enumerate(row):
            fmt = header_fmt if r_off == 0 else None
            if fmt is not None:
                worksheet.write(base_row + r_off, c_idx, value, fmt)
            else:
                worksheet.write(base_row + r_off, c_idx, value)


def _write_ok(worksheet: xlsxwriter.worksheet.Worksheet, workbook: xlsxwriter.Workbook) -> None:
    """A1 アンカー付近にテキストボックスを置き、タイトルっぽく見せる（画像は付けない）。"""
    worksheet.insert_textbox(
        "A1",
        "都道府県別人口（サンプル）\n"
        "L1-10 OK: このタイトルはセルではなく「テキストボックス」図形です（A1 付近に配置）。"
        "その下の行から表を配置。埋め込み画像の例はシート「OK-02」を参照。",
        {
            "width": 540,
            "height": 92,
            "font": {"size": 11, "bold": True},
            "align": {"vertical": "middle", "horizontal": "left"},
            "fill": {"color": "#F5F5F5"},
            "line": {"color": "#B0B0B0", "width": 1},
        },
    )
    _write_table_xlsx(worksheet, workbook, start_row_1based=_TABLE_START_ROW_OK)


def _write_ok02(worksheet: xlsxwriter.worksheet.Worksheet, workbook: xlsxwriter.Workbook) -> None:
    """表は A1 始まり。オレンジ矩形は秋田県行（ヘッダー + 5 行目 = 行6）の D 列付近。"""
    _write_table_xlsx(worksheet, workbook, start_row_1based=_TABLE_START_ROW_OK02)
    worksheet.set_column("D:D", 24)
    img = BytesIO(_png_bytes_orange())
    akita_row = _TABLE_START_ROW_OK02 + 5
    worksheet.insert_image(
        f"D{akita_row}",
        "",
        {
            "image_data": img,
            "width": 140,
            "height": 105,
            "x_offset": 24,
            "y_offset": 8,
        },
    )


def _write_ng02(worksheet: xlsxwriter.worksheet.Worksheet, workbook: xlsxwriter.Workbook) -> None:
    """欠落セル + テキストボックスで表とオブジェクトが重なるケース（参照: rule_10_excel_objects_2 NG-02）。"""
    rows = _table_rows()
    header_fmt = workbook.add_format({"bold": True})
    base_row = _TABLE_START_ROW_OK02 - 1
    for r_off, row in enumerate(rows):
        excel_row = base_row + r_off
        if r_off == _MISSING_PREF_LABEL_ROW_OFFSET:
            worksheet.write(excel_row, 1, row[1])
            worksheet.write(excel_row, 2, row[2])
            continue
        for c_idx, value in enumerate(row):
            fmt = header_fmt if r_off == 0 else None
            if fmt is not None:
                worksheet.write(excel_row, c_idx, value, fmt)
            else:
                worksheet.write(excel_row, c_idx, value)

    # 表データの後にテキストボックスを追加（描画は後から順に積まれる）。オフセットは XlsxWriter のピクセル単位。
    worksheet.insert_textbox(
        "A2",
        "青　森",
        {
            "width": 72,
            "height": 23,
            "x_offset": 5,
            "y_offset": 17,
            "font": {"size": 11, "bold": True},
            "align": {"vertical": "middle", "horizontal": "left"},
            "line": {"color": "#B0B0B0", "width": 1},
        },
    )


def _write_ng(worksheet: xlsxwriter.worksheet.Worksheet, workbook: xlsxwriter.Workbook) -> None:
    """タイトルなし。表は A1 始まり。都道府県列に枠線のみの正方形（PNG）を 1 個だけ（例: A2）。"""
    _write_table_xlsx(worksheet, workbook, start_row_1based=_TABLE_START_ROW_NG)
    # 先頭データ行（北海道）のセルに 1 個のみ
    worksheet.insert_image(
        "A2",
        "",
        {
            "image_data": BytesIO(_png_bytes_square_outline()),
            "width": 24,
            "height": 24,
            "x_offset": 2,
            "y_offset": 2,
        },
    )


def generate(output_dir: Path) -> list[Path]:
    path = output_dir / "rule_10_excel_objects.xlsx"
    workbook = xlsxwriter.Workbook(str(path))

    ws_ok1 = workbook.add_worksheet("OK-01")
    _write_ok(ws_ok1, workbook)

    ws_ok2 = workbook.add_worksheet("OK-02")
    _write_ok02(ws_ok2, workbook)

    ws_ng = workbook.add_worksheet("NG-01")
    _write_ng(ws_ng, workbook)

    ws_ng2 = workbook.add_worksheet("NG-02")
    _write_ng02(ws_ng2, workbook)

    workbook.close()
    return [path]
