"""parse_cell_range のフォーマットサポート確認テスト。"""

from harunobu.ui.components.excel_grid import parse_cell_range

BOUNDS = (1, 1, 10, 5)  # 1..10 行 x 1..5 列


class TestParseCellRange:
    def test_a1_single(self):
        assert parse_cell_range("A1") == [(1, 1)]

    def test_a1_range(self):
        cells = parse_cell_range("A1:B2")
        assert sorted(cells) == [(1, 1), (1, 2), (2, 1), (2, 2)]

    def test_rxcx(self):
        assert parse_cell_range("R3C5") == [(3, 5)]

    def test_row_n(self):
        cells = parse_cell_range("行2", table_bounds=BOUNDS)
        assert cells == [(2, 1), (2, 2), (2, 3), (2, 4), (2, 5)]

    def test_row_range(self):
        cells = parse_cell_range("行2-3", table_bounds=BOUNDS)
        assert len(cells) == 10  # 2 行 x 5 列

    def test_col_n(self):
        cells = parse_cell_range("列5", table_bounds=BOUNDS)
        assert len(cells) == 10  # 10 行 x 1 列

    def test_row_only_n_n(self):
        cells = parse_cell_range("12:12", table_bounds=(12, 1, 12, 3))
        assert sorted(cells) == [(12, 1), (12, 2), (12, 3)]

    def test_invalid_returns_empty(self):
        assert parse_cell_range("???") == []

    def test_empty_returns_empty(self):
        assert parse_cell_range("") == []

    def test_row_without_bounds_returns_empty(self):
        assert parse_cell_range("行2") == []

    def test_col_without_bounds_returns_empty(self):
        assert parse_cell_range("列5") == []

    def test_row_only_without_bounds_returns_empty(self):
        assert parse_cell_range("12:12") == []
