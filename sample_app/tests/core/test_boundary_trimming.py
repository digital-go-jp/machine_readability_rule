"""境界トリミング・others 分離のテスト"""

from __future__ import annotations

from harunobu.core.layout.island import IslandDetector, _trim_boundaries
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
    formulas: dict[tuple[int, int], str] | None = None,
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

            formula = None
            if formulas and (r_idx, c_idx) in formulas:
                formula = formulas[(r_idx, c_idx)]

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
                formula=formula,
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


class TestTrimBoundariesTitle:
    """タイトル行トリミングのテスト"""

    def test_title_row_trimmed(self):
        """先頭行が1セルのみ非空でテーブル幅3+列 → タイトル行としてトリミング"""
        sheet = _make_sheet(
            [
                ["人口統計データ", None, None, None],
                ["都道府県", "2020年", "2021年", "2022年"],
                ["東京", 100, 200, 300],
                ["大阪", 50, 60, 70],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 4, 1, 4)

        assert start == 2
        assert end == 4
        assert len(others) == 1
        assert others[0].region_type == "title"
        assert others[0].value == "人口統計データ"

    def test_no_title_when_narrow(self):
        """2列のテーブルではタイトル行トリミングしない"""
        sheet = _make_sheet(
            [
                ["タイトル", None],
                ["A", 1],
                ["B", 2],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 3, 1, 2)

        assert start == 1  # トリミングされない
        assert end == 3
        assert len(others) == 0

    def test_no_title_when_full_row(self):
        """先頭行が全セル非空 → タイトルではない"""
        sheet = _make_sheet(
            [
                ["A", "B", "C"],
                ["D", 1, 2],
                ["E", 3, 4],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 3, 1, 3)

        assert start == 1
        assert end == 3
        assert len(others) == 0


class TestTrimBoundariesTotal:
    """合計行トリミングのテスト"""

    def test_sum_formula_trimmed(self):
        """=SUM数式を含む末尾行 → 合計行としてトリミング"""
        sheet = _make_sheet(
            [
                ["名前", "値"],
                ["A", 100],
                ["B", 200],
                ["合計", 300],
            ],
            formulas={(4, 2): "=SUM(B2:B3)"},
        )
        start, end, others = _trim_boundaries(sheet, 1, 4, 1, 2)

        assert start == 1
        assert end == 3
        total_others = [o for o in others if o.region_type == "total"]
        assert len(total_others) == 2  # "合計" と 300

    def test_subtotal_formula_trimmed(self):
        """=SUBTOTAL 数式も合計行として検出"""
        sheet = _make_sheet(
            [
                ["名前", "値"],
                ["A", 100],
                ["小計", 100],
            ],
            formulas={(3, 2): "=SUBTOTAL(9,B2:B2)"},
        )
        start, end, others = _trim_boundaries(sheet, 1, 3, 1, 2)

        assert end == 2
        total_others = [o for o in others if o.region_type == "total"]
        assert len(total_others) == 2


class TestTrimBoundariesNote:
    """備考行トリミングのテスト"""

    def test_note_row_trimmed(self):
        """「※」で始まる末尾行 → 備考行としてトリミング"""
        sheet = _make_sheet(
            [
                ["名前", "値", "備考"],
                ["A", 100, "x"],
                ["B", 200, "y"],
                ["※このデータは暫定値です", None, None],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 4, 1, 3)

        assert end == 3
        note_others = [o for o in others if o.region_type == "note"]
        assert len(note_others) == 1
        assert "暫定値" in str(note_others[0].value)

    def test_multiple_notes_trimmed(self):
        """複数の備考行が連続している場合"""
        sheet = _make_sheet(
            [
                ["名前", "値", "備考"],
                ["A", 100, "x"],
                ["※注1", None, None],
                ["※注2", None, None],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 4, 1, 3)

        assert end == 2
        note_others = [o for o in others if o.region_type == "note"]
        assert len(note_others) == 2


class TestTrimBoundariesSource:
    """出典行トリミングのテスト"""

    def test_source_row_trimmed(self):
        """「出典：」で始まる充填率低い末尾行 → 出典行としてトリミング"""
        sheet = _make_sheet(
            [
                ["名前", "値", "備考", "補足"],
                ["A", 100, "x", "y"],
                ["出典：総務省統計局", None, None, None],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 3, 1, 4)

        assert end == 2
        source_others = [o for o in others if o.region_type == "source"]
        assert len(source_others) == 1
        assert "総務省" in str(source_others[0].value)


class TestTrimBoundariesCombined:
    """複合トリミングのテスト"""

    def test_title_and_note(self):
        """タイトル行 + 備考行の両方をトリミング"""
        sheet = _make_sheet(
            [
                ["人口データ", None, None],
                ["都道府県", "人口", "面積"],
                ["東京", 100, 200],
                ["※暫定値", None, None],
            ]
        )
        start, end, others = _trim_boundaries(sheet, 1, 4, 1, 3)

        assert start == 2
        assert end == 3
        title_others = [o for o in others if o.region_type == "title"]
        note_others = [o for o in others if o.region_type == "note"]
        assert len(title_others) == 1
        assert len(note_others) == 1


class TestDetectWithOthers:
    """IslandDetector.detect_with_others の統合テスト"""

    def test_others_from_title(self):
        """タイトル行が others に含まれる"""
        sheet = _make_sheet(
            [
                ["統計データ", None, None, None],
                ["名前", "A", "B", "C"],
                ["X", 1, 2, 3],
                ["Y", 4, 5, 6],
            ],
            bold_cells={(2, 1), (2, 2), (2, 3), (2, 4)},
        )
        detector = IslandDetector()
        result = detector.detect_with_others(sheet)

        assert len(result.tables) == 1
        assert result.tables[0].range.start_row == 2
        title_others = [o for o in result.others if o.region_type == "title"]
        assert len(title_others) == 1
        assert title_others[0].value == "統計データ"

    def test_backward_compat_detect(self):
        """detect() は引き続き list[TableRegion] を返す"""
        sheet = _make_sheet(
            [
                ["名前", "値"],
                ["A", 1],
            ],
            bold_cells={(1, 1), (1, 2)},
        )
        detector = IslandDetector()
        regions = detector.detect(sheet)

        assert isinstance(regions, list)
        assert len(regions) == 1

    def test_note_trimmed_from_detect(self):
        """備考行がトリミングされた結果、テーブル範囲が狭まる"""
        sheet = _make_sheet(
            [
                ["名前", "値", "備考"],
                ["A", 100, "x"],
                ["B", 200, "y"],
                ["※データは暫定", None, None],
            ],
            bold_cells={(1, 1), (1, 2), (1, 3)},
        )
        detector = IslandDetector()
        result = detector.detect_with_others(sheet)

        assert len(result.tables) == 1
        assert result.tables[0].range.end_row == 3  # 備考行がトリミングされた
        note_others = [o for o in result.others if o.region_type == "note"]
        assert len(note_others) == 1
