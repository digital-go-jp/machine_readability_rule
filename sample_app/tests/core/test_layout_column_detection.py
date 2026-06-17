"""ColumnHeader 生成・列型推定のテスト"""

from __future__ import annotations

import pytest

from harunobu.core.layout.island import (
    IslandDetector,
    _determine_column_type,
    _generate_column_headers,
    _infer_column_schemas,
    _is_date_string,
)
from harunobu.core.models import (
    Cell,
    CellFormat,
    CellPosition,
    MergedRange,
    Sheet,
)


def _make_sheet(
    rows: list[list],
    *,
    merged_cells: list[MergedRange] | None = None,
    bold_cells: set[tuple[int, int]] | None = None,
) -> Sheet:
    """テスト用シートを作成するヘルパー"""
    cells: dict[tuple[int, int], Cell] = {}
    max_row = len(rows)
    max_col = max((len(r) for r in rows), default=0)

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, value in enumerate(row, start=1):
            fmt = CellFormat()
            if bold_cells and (r_idx, c_idx) in bold_cells:
                fmt = CellFormat(bold=True)

            is_merged = False
            merge_master = None
            if merged_cells:
                for mc in merged_cells:
                    if mc.start_row <= r_idx <= mc.end_row and mc.start_col <= c_idx <= mc.end_col:
                        is_merged = True
                        if r_idx != mc.start_row or c_idx != mc.start_col:
                            merge_master = CellPosition(row=mc.start_row, col=mc.start_col)
                        break

            cells[(r_idx, c_idx)] = Cell(
                pos=CellPosition(row=r_idx, col=c_idx),
                value=value,
                fmt=fmt,
                is_merged=is_merged,
                merge_master=merge_master,
            )

    return Sheet(
        name="TestSheet",
        cells=cells,
        merged_cells=merged_cells or [],
        max_row=max_row,
        max_col=max_col,
    )


# ─── _generate_column_headers テスト ───


class TestGenerateColumnHeaders:
    def test_single_header_row(self):
        """単一ヘッダー行から ColumnHeader を生成"""
        sheet = _make_sheet(
            [
                ["名前", "年齢", "住所"],
                ["田中", 30, "東京"],
                ["佐藤", 25, "大阪"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 3)

        assert len(headers) == 3
        assert headers[0].label == "名前"
        assert headers[0].col_index == 1
        assert headers[0].header_rows == [1]
        assert headers[0].is_merged is False
        assert headers[1].label == "年齢"
        assert headers[2].label == "住所"

    def test_multi_row_header(self):
        """マルチ行ヘッダーのラベル結合"""
        sheet = _make_sheet(
            [
                ["基本情報", "基本情報", "連絡先"],
                ["氏名", "年齢", "電話番号"],
                ["田中", 30, "090-1234"],
            ]
        )
        headers = _generate_column_headers(sheet, [1, 2], 1, 3)

        assert len(headers) == 3
        assert headers[0].label == "基本情報 / 氏名"
        assert headers[0].header_rows == [1, 2]
        assert headers[1].label == "基本情報 / 年齢"
        assert headers[2].label == "連絡先 / 電話番号"

    def test_merged_header(self):
        """結合セルヘッダーの検出 + 値伝播"""
        merged = [MergedRange(start_row=1, start_col=1, end_row=1, end_col=2)]
        sheet = _make_sheet(
            [
                ["基本情報", None, "備考"],
                ["田中", 30, "特になし"],
            ],
            merged_cells=merged,
        )
        headers = _generate_column_headers(sheet, [1], 1, 3)

        assert headers[0].is_merged is True
        assert headers[0].label == "基本情報"
        assert headers[1].is_merged is True  # 結合範囲内
        assert headers[1].label == "基本情報"  # マスターセルから値伝播
        assert headers[2].is_merged is False

    def test_merged_multi_row_header_propagation(self):
        """マルチ行ヘッダーでの結合セル値伝播"""
        merged = [MergedRange(start_row=1, start_col=2, end_row=1, end_col=4)]
        sheet = _make_sheet(
            [
                ["都道府県", "人口推移", None, None],
                ["都道府県", "2020年", "2021年", "2022年"],
                ["東京", 100, 200, 300],
            ],
            merged_cells=merged,
        )
        headers = _generate_column_headers(sheet, [1, 2], 1, 4)

        assert headers[0].label == "都道府県"  # 重複するが同値なので1回のみ
        assert headers[1].label == "人口推移 / 2020年"
        assert headers[2].label == "人口推移 / 2021年"
        assert headers[3].label == "人口推移 / 2022年"

    def test_empty_header_rows(self):
        """空のヘッダー行リストでは空リストを返す"""
        sheet = _make_sheet([["A", "B"]])
        headers = _generate_column_headers(sheet, [], 1, 2)
        assert headers == []

    def test_header_with_none_values(self):
        """None値を含むヘッダー"""
        sheet = _make_sheet(
            [
                ["名前", None, "住所"],
                ["田中", 30, "東京"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 3)

        assert headers[0].label == "名前"
        assert headers[1].label == ""  # None値はラベルなし
        assert headers[2].label == "住所"


# ─── _infer_column_schemas テスト ───


class TestInferColumnSchemas:
    def test_numeric_column(self):
        """数値列の型推定"""
        sheet = _make_sheet(
            [
                ["値"],
                [100],
                [200],
                [300],
                [400],
                [500],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 1)
        schemas = _infer_column_schemas(sheet, 2, 6, 1, 1, headers)

        assert len(schemas) == 1
        assert schemas[0].inferred_type == "numeric"
        assert schemas[0].has_header is True

    def test_text_column(self):
        """文字列列の型推定"""
        sheet = _make_sheet(
            [
                ["名前"],
                ["田中"],
                ["佐藤"],
                ["鈴木"],
                ["高橋"],
                ["伊藤"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 1)
        schemas = _infer_column_schemas(sheet, 2, 6, 1, 1, headers)

        assert schemas[0].inferred_type == "text"

    def test_date_column(self):
        """日付列の型推定"""
        sheet = _make_sheet(
            [
                ["日付"],
                ["2024-01-01"],
                ["2024-02-15"],
                ["2024-03-20"],
                ["2024-04-10"],
                ["2024-05-05"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 1)
        schemas = _infer_column_schemas(sheet, 2, 6, 1, 1, headers)

        assert schemas[0].inferred_type == "date"

    def test_date_slash_format(self):
        """スラッシュ区切り日付の型推定"""
        sheet = _make_sheet(
            [
                ["日付"],
                ["2024/01/01"],
                ["2024/02/15"],
                ["2024/03/20"],
                ["2024/04/10"],
                ["2024/05/05"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 1)
        schemas = _infer_column_schemas(sheet, 2, 6, 1, 1, headers)

        assert schemas[0].inferred_type == "date"

    def test_mixed_column(self):
        """混在列の型推定"""
        sheet = _make_sheet(
            [
                ["値"],
                [100],
                ["テキスト"],
                [200],
                ["2024-01-01"],
                ["abc"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 1)
        schemas = _infer_column_schemas(sheet, 2, 6, 1, 1, headers)

        assert schemas[0].inferred_type == "mixed"

    def test_empty_column(self):
        """空列の型推定"""
        sheet = _make_sheet(
            [
                ["値"],
                [None],
                [None],
                [None],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 1)
        schemas = _infer_column_schemas(sheet, 2, 4, 1, 1, headers)

        assert schemas[0].inferred_type == "empty"

    def test_no_header_column(self):
        """ヘッダーなし列の has_header 判定"""
        sheet = _make_sheet(
            [
                ["名前", None],
                ["田中", 100],
                ["佐藤", 200],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 2)
        schemas = _infer_column_schemas(sheet, 2, 3, 1, 2, headers)

        assert schemas[0].has_header is True
        assert schemas[1].has_header is False

    def test_multiple_columns(self):
        """複数列の型推定"""
        sheet = _make_sheet(
            [
                ["名前", "年齢", "入社日"],
                ["田中", 30, "2020-04-01"],
                ["佐藤", 25, "2021-04-01"],
                ["鈴木", 35, "2019-04-01"],
                ["高橋", 28, "2022-04-01"],
                ["伊藤", 40, "2018-04-01"],
            ]
        )
        headers = _generate_column_headers(sheet, [1], 1, 3)
        schemas = _infer_column_schemas(sheet, 2, 6, 1, 3, headers)

        assert schemas[0].inferred_type == "text"
        assert schemas[1].inferred_type == "numeric"
        assert schemas[2].inferred_type == "date"


# ─── ヘルパー関数テスト ───


class TestHelpers:
    @pytest.mark.parametrize(
        "s,expected",
        [
            ("2024-01-01", True),
            ("2024/01/01", True),
            ("2024-1-1", True),
            ("01/31/2024", True),
            ("not-a-date", False),
            ("2024", False),
            ("", False),
        ],
    )
    def test_is_date_string(self, s: str, expected: bool):
        assert _is_date_string(s) == expected

    def test_determine_column_type_numeric(self):
        counts = {"numeric": 10, "text": 0, "date": 0, "empty": 2}
        assert _determine_column_type(counts) == "numeric"

    def test_determine_column_type_all_empty(self):
        counts = {"numeric": 0, "text": 0, "date": 0, "empty": 10}
        assert _determine_column_type(counts) == "empty"

    def test_determine_column_type_mixed(self):
        counts = {"numeric": 4, "text": 3, "date": 3, "empty": 0}
        assert _determine_column_type(counts) == "mixed"


# ─── 統合テスト ───


class TestIslandDetectorIntegration:
    def test_column_headers_in_detected_regions(self):
        """IslandDetector が ColumnHeader を含む TableRegion を返す"""
        sheet = _make_sheet(
            [
                ["名前", "年齢", "住所"],
                ["田中", 30, "東京"],
                ["佐藤", 25, "大阪"],
            ],
            bold_cells={(1, 1), (1, 2), (1, 3)},
        )
        detector = IslandDetector()
        regions = detector.detect(sheet)

        assert len(regions) == 1
        region = regions[0]
        assert len(region.layout.column_headers) == 3
        assert region.layout.column_headers[0].label == "名前"
        assert len(region.layout.columns) == 3
        assert region.layout.columns[0].inferred_type == "text"
        assert region.layout.columns[1].inferred_type == "numeric"

    def test_column_headers_with_multi_row(self):
        """マルチ行ヘッダーのテーブル検出"""
        merged = [MergedRange(start_row=1, start_col=1, end_row=1, end_col=2)]
        sheet = _make_sheet(
            [
                ["基本情報", None, "備考"],
                ["氏名", "年齢", "メモ"],
                ["田中", 30, "特になし"],
                ["佐藤", 25, "特になし"],
            ],
            merged_cells=merged,
            bold_cells={(1, 1), (1, 3), (2, 1), (2, 2), (2, 3)},
        )
        detector = IslandDetector()
        regions = detector.detect(sheet)

        assert len(regions) == 1
        region = regions[0]
        assert region.layout.header_rows == [1, 2]
        assert len(region.layout.column_headers) == 3
        assert region.layout.column_headers[0].label == "基本情報 / 氏名"
        assert region.layout.column_headers[0].is_merged is True
