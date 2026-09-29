"""レイアウトヘッダー検出のテスト

IslandDetector のマルチ行ヘッダー検出、結合セル対応、
gap_threshold 設定可能性をテストする。
"""

from __future__ import annotations

from harunobu.core.layout.detector import LayoutDetector
from harunobu.core.layout.island import (
    IslandDetector,
    _estimate_layout,
    _has_merged_cells_in_range,
    _is_header_row,
)
from harunobu.core.models import (
    Cell,
    CellFormat,
    CellPosition,
    Config,
    MergedRange,
    Sheet,
)


def _make_sheet(
    rows_data: list[list],
    *,
    bold_rows: set[int] | None = None,
    merged_cells: list[MergedRange] | None = None,
    name: str = "Sheet1",
) -> Sheet:
    """テスト用シートを生成するヘルパー。

    rows_data: 行データのリスト (1-indexed で格納)
    bold_rows: 太字にする行番号のセット (1-indexed)
    merged_cells: 結合セル範囲のリスト
    """
    cells: dict[tuple[int, int], Cell] = {}
    max_row = len(rows_data)
    max_col = max((len(row) for row in rows_data), default=0)
    bold_rows = bold_rows or set()

    for r_idx, row in enumerate(rows_data, start=1):
        for c_idx, value in enumerate(row, start=1):
            is_bold = r_idx in bold_rows
            fmt = CellFormat(bold=is_bold)
            is_merged = False
            merge_master = None
            if merged_cells:
                for mr in merged_cells:
                    if mr.start_row <= r_idx <= mr.end_row and mr.start_col <= c_idx <= mr.end_col:
                        is_merged = True
                        if r_idx != mr.start_row or c_idx != mr.start_col:
                            merge_master = CellPosition(row=mr.start_row, col=mr.start_col)
                        break
            cells[(r_idx, c_idx)] = Cell(
                pos=CellPosition(row=r_idx, col=c_idx),
                value=value,
                fmt=fmt,
                is_merged=is_merged,
                merge_master=merge_master,
            )

    return Sheet(
        name=name,
        cells=cells,
        merged_cells=merged_cells or [],
        max_row=max_row,
        max_col=max_col,
    )


# ─── _is_header_row のテスト ───


class TestIsHeaderRow:
    """_is_header_row ヘルパー関数のテスト。"""

    def test_bold_row_is_header(self):
        sheet = _make_sheet([["名前", "年齢"]], bold_rows={1})
        assert _is_header_row(sheet, 1, 1, 2) is True

    def test_all_string_row_is_header(self):
        sheet = _make_sheet([["名前", "住所", "電話番号"]])
        assert _is_header_row(sheet, 1, 1, 3) is True

    def test_numeric_row_is_not_header(self):
        sheet = _make_sheet([[1, 2, 3]])
        assert _is_header_row(sheet, 1, 1, 3) is False

    def test_mixed_row_is_not_header(self):
        sheet = _make_sheet([["名前", 100, "住所"]])
        assert _is_header_row(sheet, 1, 1, 3) is False

    def test_merged_cell_row_is_header(self):
        merged = [MergedRange(start_row=1, start_col=1, end_row=1, end_col=3)]
        sheet = _make_sheet([["カテゴリ", None, None]], merged_cells=merged)
        assert _is_header_row(sheet, 1, 1, 3) is True

    def test_empty_row_is_not_header(self):
        sheet = _make_sheet([[None, None, None]])
        assert _is_header_row(sheet, 1, 1, 3) is False


# ─── _has_merged_cells_in_range のテスト ───


class TestHasMergedCellsInRange:
    def test_merged_in_range(self):
        merged = [MergedRange(start_row=1, start_col=1, end_row=1, end_col=3)]
        sheet = _make_sheet([["A", None, None]], merged_cells=merged)
        assert _has_merged_cells_in_range(sheet, 1, 1, 1, 3) is True

    def test_no_merged_in_range(self):
        sheet = _make_sheet([["A", "B", "C"]])
        assert _has_merged_cells_in_range(sheet, 1, 1, 1, 3) is False

    def test_merged_outside_range(self):
        merged = [MergedRange(start_row=5, start_col=5, end_row=5, end_col=7)]
        sheet = _make_sheet(
            [["A", "B", "C"], [1, 2, 3]],
            merged_cells=merged,
        )
        assert _has_merged_cells_in_range(sheet, 1, 2, 1, 3) is False


# ─── 単一行ヘッダー検出（後方互換性） ───


class TestSingleRowHeader:
    """従来の単一行ヘッダー検出が維持されていることを確認。"""

    def test_bold_single_header(self):
        sheet = _make_sheet(
            [["名前", "年齢"], ["太郎", 20], ["花子", 25]],
            bold_rows={1},
        )
        layout = _estimate_layout(sheet, 1, 3, 1, 2)
        assert layout.header_rows == [1]
        assert layout.body_start_row == 2
        assert layout.body_end_row == 3

    def test_all_string_single_header(self):
        sheet = _make_sheet(
            [["名前", "住所"], ["太郎", "東京"], ["花子", "大阪"]],
        )
        layout = _estimate_layout(sheet, 1, 3, 1, 2)
        assert layout.header_rows == [1]
        assert layout.body_start_row == 2

    def test_single_row_no_header(self):
        sheet = _make_sheet([[1, 2, 3]])
        layout = _estimate_layout(sheet, 1, 1, 1, 3)
        assert layout.header_rows == []
        assert layout.body_start_row == 1


# ─── マルチ行ヘッダー検出 ───


class TestMultiRowHeader:
    """マルチ行ヘッダー検出のテスト。"""

    def test_two_row_bold_header(self):
        """2行の太字ヘッダーを検出する。"""
        sheet = _make_sheet(
            [
                ["大分類", "小分類", "値"],  # ヘッダー行 1
                ["カテゴリA", "サブ1", "数量"],  # ヘッダー行 2
                ["item1", "sub1", 100],  # データ
                ["item2", "sub2", 200],  # データ
            ],
            bold_rows={1, 2},
        )
        layout = _estimate_layout(sheet, 1, 4, 1, 3)
        assert layout.header_rows == [1, 2]
        assert layout.body_start_row == 3
        assert layout.body_end_row == 4

    def test_three_row_string_header(self):
        """3行の文字列ヘッダーを検出する。"""
        sheet = _make_sheet(
            [
                ["都道府県別", "人口統計", "概要"],  # ヘッダー 1
                ["地域", "区分", "種別"],  # ヘッダー 2
                ["市区町村", "男女", "年齢層"],  # ヘッダー 3
                ["東京都", "男", 1000],  # データ
            ],
        )
        layout = _estimate_layout(sheet, 1, 4, 1, 3)
        assert layout.header_rows == [1, 2, 3]
        assert layout.body_start_row == 4
        assert layout.body_end_row == 4

    def test_mixed_header_bold_then_string(self):
        """太字行の後に文字列行が続くヘッダー。"""
        sheet = _make_sheet(
            [
                ["統計表タイトル", "2024年度", "全国"],  # 太字ヘッダー
                ["項目", "単位", "備考"],  # 文字列ヘッダー
                ["GDP", 100.5, "速報値"],  # データ
            ],
            bold_rows={1},
        )
        layout = _estimate_layout(sheet, 1, 3, 1, 3)
        assert layout.header_rows == [1, 2]
        assert layout.body_start_row == 3

    def test_header_stops_at_data_row(self):
        """ヘッダー検出はデータ行で止まる。"""
        sheet = _make_sheet(
            [
                ["名前", "年齢", "住所"],  # ヘッダー
                ["太郎", 20, "東京"],  # データ（型混在 → ヘッダーではない）
                ["花子", 25, "大阪"],
            ],
        )
        layout = _estimate_layout(sheet, 1, 3, 1, 3)
        assert layout.header_rows == [1]
        assert layout.body_start_row == 2

    def test_max_header_rows_limit(self):
        """max_header_rows で制限される（太字=強シグナル使用）。"""
        sheet = _make_sheet(
            [
                ["H1", "H1", "H1"],
                ["H2", "H2", "H2"],
                ["H3", "H3", "H3"],
                ["H4", "H4", "H4"],  # ヘッダーになり得るが上限を超える
                ["data", "data", 100],
            ],
            bold_rows={1, 2, 3, 4},
        )
        # max_header_rows=2 に制限
        layout = _estimate_layout(sheet, 1, 5, 1, 3, max_header_rows=2)
        assert layout.header_rows == [1, 2]
        assert layout.body_start_row == 3


# ─── 結合セルヘッダー検出 ───


class TestMergedCellHeader:
    """結合セルを含むヘッダー検出。"""

    def test_merged_header_row(self):
        """結合セルを持つヘッダー行を検出する。"""
        merged = [MergedRange(start_row=1, start_col=1, end_row=1, end_col=3)]
        sheet = _make_sheet(
            [
                ["統計データ", None, None],  # 結合ヘッダー
                ["項目", "値", "備考"],  # サブヘッダー
                ["A", 100, "注1"],  # データ
            ],
            merged_cells=merged,
        )
        layout = _estimate_layout(sheet, 1, 3, 1, 3)
        assert 1 in layout.header_rows
        assert 2 in layout.header_rows
        assert layout.body_start_row == 3

    def test_vertical_merged_extends_header(self):
        """縦方向の結合セルがヘッダー範囲を拡張する。"""
        merged = [MergedRange(start_row=1, start_col=1, end_row=2, end_col=1)]
        sheet = _make_sheet(
            [
                ["カテゴリ", "サブ1", "サブ2"],  # row 1: 結合 + 文字列
                [None, "詳細1", "詳細2"],  # row 2: 結合継続 + 文字列
                ["A", 10, 20],  # データ
            ],
            merged_cells=merged,
        )
        layout = _estimate_layout(sheet, 1, 3, 1, 3)
        assert layout.header_rows == [1, 2]
        assert layout.body_start_row == 3

    def test_government_style_multi_row_header(self):
        """政府系Excelでよくある複合ヘッダー。"""
        merged = [
            MergedRange(start_row=1, start_col=1, end_row=1, end_col=4),  # タイトル行
            MergedRange(start_row=2, start_col=1, end_row=2, end_col=2),  # サブヘッダー
            MergedRange(start_row=2, start_col=3, end_row=2, end_col=4),  # サブヘッダー
        ]
        sheet = _make_sheet(
            [
                ["令和5年度 都道府県別統計", None, None, None],
                ["人口", None, "世帯数", None],
                ["都道府県", "総人口", "一般世帯", "単独世帯"],
                ["北海道", 5200000, 2700000, 900000],
            ],
            bold_rows={1, 2, 3},
            merged_cells=merged,
        )
        layout = _estimate_layout(sheet, 1, 4, 1, 4)
        assert layout.header_rows == [1, 2, 3]
        assert layout.body_start_row == 4


# ─── IslandDetector 統合テスト ───


class TestIslandDetectorGapThreshold:
    """gap_threshold の設定可能性テスト。"""

    def test_default_gap_threshold(self):
        detector = IslandDetector()
        assert detector.gap_threshold == 1

    def test_custom_gap_threshold(self):
        detector = IslandDetector(gap_threshold=3)
        assert detector.gap_threshold == 3

    def test_larger_gap_merges_islands(self):
        """gap_threshold を大きくすると離れた領域が1つの島になる。"""
        sheet = _make_sheet(
            [
                ["A", "B"],
                [1, 2],
                [None, None],  # ギャップ行
                [None, None],  # ギャップ行
                [3, 4],
            ],
        )
        # gap_threshold=1 → 2つの島
        detector_strict = IslandDetector(gap_threshold=1)
        regions_strict = detector_strict.detect(sheet)
        assert len(regions_strict) == 2

        # gap_threshold=3 → 1つの島
        detector_lenient = IslandDetector(gap_threshold=3)
        regions_lenient = detector_lenient.detect(sheet)
        assert len(regions_lenient) == 1

    def test_custom_max_header_rows(self):
        """max_header_rows パラメータが反映される。"""
        detector = IslandDetector(max_header_rows=2)
        assert detector.max_header_rows == 2


class TestIslandDetectorMultiRowHeader:
    """IslandDetector 統合テスト: マルチ行ヘッダー。"""

    def test_detect_two_row_header(self):
        """IslandDetector でマルチ行ヘッダーが検出される。"""
        sheet = _make_sheet(
            [
                ["大分類", "中分類", "値"],
                ["A区分", "B区分", "金額"],
                ["x", "y", 100],
                ["p", "q", 200],
            ],
            bold_rows={1, 2},
        )
        detector = IslandDetector()
        regions = detector.detect(sheet)
        assert len(regions) == 1
        assert regions[0].layout.header_rows == [1, 2]
        assert regions[0].layout.body_start_row == 3

    def test_detect_with_merged_header(self):
        """結合セルを持つヘッダーが正しく検出される。"""
        merged = [MergedRange(start_row=1, start_col=1, end_row=1, end_col=3)]
        sheet = _make_sheet(
            [
                ["タイトル", None, None],
                ["列A", "列B", "列C"],
                ["a", "b", 10],
            ],
            merged_cells=merged,
        )
        detector = IslandDetector()
        regions = detector.detect(sheet)
        assert len(regions) == 1
        assert 1 in regions[0].layout.header_rows
        assert 2 in regions[0].layout.header_rows


# ─── LayoutDetector 統合テスト ───


class TestLayoutDetectorHeaderDetection:
    """LayoutDetector 経由でのヘッダー検出。"""

    def test_layout_detector_multi_row_header(self):
        """LayoutDetector でもマルチ行ヘッダーが検出される。"""
        sheet = _make_sheet(
            [
                ["分類", "項目", "数値"],
                ["大", "小", "合計"],
                ["A", "a1", 100],
                ["B", "b1", 200],
            ],
            bold_rows={1, 2},
        )
        config = Config(mode="lite", confidence_threshold=0.0)
        detector = LayoutDetector(config=config)
        regions = detector.detect(sheet)
        assert len(regions) >= 1
        region = regions[0]
        assert region.layout.header_rows == [1, 2]
