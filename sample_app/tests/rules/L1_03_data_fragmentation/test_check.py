"""L1-03: データ分断チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.core.models import (
    CellRange,
    TableContext,
    TableLayout,
    TableRegion,
)
from harunobu.rules.level1.L1_03_data_fragmentation import DataFragmentationRule


def _make_region(start_row: int, end_row: int, start_col: int, end_col: int) -> TableRegion:
    """テスト用 TableRegion を組み立てる。"""
    return TableRegion(
        range=CellRange(
            start_row=start_row,
            start_col=start_col,
            end_row=end_row,
            end_col=end_col,
        ),
        layout=TableLayout(
            header_rows=[start_row],
            body_start_row=start_row + 1,
            body_end_row=end_row,
        ),
        confidence=1.0,
    )


class TestDataFragmentationCheck:
    """L1-03 データ分断チェック"""

    @pytest.fixture
    def rule(self):
        return DataFragmentationRule()

    def test_no_fragmentation_passes(self, rule, create_context):
        """空白行・列がない場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_empty_row_detected(self, rule, create_context):
        """データ範囲内の空白行が検出される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢"],
                    [None, None],  # 空白行
                    ["花子", 25],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) >= 1
        # assert result.score < 100

    def test_empty_column_detected(self, rule, create_context):
        """データ範囲内の空白列が検出される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", None, "年齢"],
                    ["太郎", None, 20],
                    ["花子", None, 25],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        # 空白列1件
        assert any("列" in v.cell_range for v in result.violations)

    def test_score_decreases_with_more_violations(self, rule, create_context):
        """違反数が増えるとスコアが下がる"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", None, "年齢"],
                    [None, None, None],  # 空白行
                    ["花子", None, 25],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        # 空白行1件 + 空白列1件 = 2件 -> 100 - 2*10 = 80
        # assert result.score == 80

    def test_merged_col_span_not_flagged_as_empty(self, rule, create_context):
        """列方向の結合セルの従属列（非マスター列）は空白列として検出されない。

        例: A1:B1 が結合されている場合、B列は非マスターのため「空列」ではない。
        """
        ctx = create_context(
            {
                "Sheet1": [
                    ["項目名", None, "値"],  # A1:B1 merged（B1は非マスター）
                    ["データA", None, 100],  # A2:B2 merged
                    ["データB", None, 200],  # A3:B3 merged
                ]
            },
            merged_cells=[
                {"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 1, "end_col": 2},
                {"sheet": "Sheet1", "start_row": 2, "start_col": 1, "end_row": 2, "end_col": 2},
                {"sheet": "Sheet1", "start_row": 3, "start_col": 1, "end_row": 3, "end_col": 2},
            ],
        )
        result = rule.check(ctx)
        # 列2（B列）はすべて結合セルの非マスター → FPとして報告されない
        assert result.passed is True
        assert len(result.violations) == 0

    def test_row_span_merged_col_still_checked(self, rule, create_context):
        """行方向の結合セル（同一列内）を持つ列は空白列チェックの対象のまま。

        例: A1:A3 が結合（行スパン）されていても、列A全体が空白ならば検出される。
        """
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", None, "値"],
                    [None, None, 100],
                    [None, None, 200],
                ]
            },
            merged_cells=[
                # A1:A3 は行スパン結合（同一列）- 列B(col=2)は真の空白列
                {"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 3, "end_col": 1},
            ],
        )
        result = rule.check(ctx)
        # 列2（B列）は本当に空白 → 検出される
        assert result.passed is False
        assert any("列" in v.cell_range for v in result.violations)


class TestInterTableFragmentation:
    """L1-03 テーブル間空白行検出（gap_threshold 非依存化）"""

    @pytest.fixture
    def rule(self):
        return DataFragmentationRule()

    def _ctx_with_two_tables(
        self,
        create_workbook,
        sheets_data: dict,
        first: TableRegion,
        second: TableRegion,
        current_index: int = 0,
    ) -> TableContext:
        """2 テーブルのシートに対する TableContext を生成する。

        current_index で「現在処理中のテーブル」を切り替えられる。
        """
        workbook = create_workbook(sheets_data=sheets_data)
        sheet = workbook.sheets[0]
        all_tables = [first, second]
        return TableContext(
            workbook=workbook,
            sheet=sheet,
            table_region=all_tables[current_index],
            all_tables=all_tables,
        )

    def test_inter_table_empty_row_detected(self, rule, create_workbook):
        """レイアウト推定が 2 行以上の空行で分割した 2 テーブル間の空行が検出される。"""
        sheets_data = {
            "Sheet1": [
                ["名前", "年齢"],
                ["太郎", 20],
                ["花子", 25],
                [None, None],  # 空行（行4）
                [None, None],  # 空行（行5）
                ["名前", "年齢"],
                ["次郎", 30],
            ]
        }
        first = _make_region(1, 3, 1, 2)
        second = _make_region(6, 7, 1, 2)
        ctx = self._ctx_with_two_tables(create_workbook, sheets_data, first, second)

        result = rule.check(ctx)
        assert result.passed is False
        inter_rows = [v.cell_range for v in result.violations if "行4" in v.cell_range or "行5" in v.cell_range]
        assert "行4" in inter_rows
        assert "行5" in inter_rows
        assert any("テーブル間" in v.description for v in result.violations)

    def test_inter_table_check_runs_only_on_first_table(self, rule, create_workbook):
        """2 番目のテーブルに対する check ではテーブル間空行違反を二重報告しない。"""
        sheets_data = {
            "Sheet1": [
                ["名前", "年齢"],
                ["太郎", 20],
                ["花子", 25],
                [None, None],
                [None, None],
                ["名前", "年齢"],
                ["次郎", 30],
            ]
        }
        first = _make_region(1, 3, 1, 2)
        second = _make_region(6, 7, 1, 2)
        ctx_second = self._ctx_with_two_tables(create_workbook, sheets_data, first, second, current_index=1)

        result = rule.check(ctx_second)
        # 2 番目のテーブル自体は空行・空列を持たない & テーブル間判定は dedupe → pass
        assert result.passed is True
        assert all("テーブル間" not in v.description for v in result.violations)

    def test_inter_table_no_overlap_columns_still_flagged(self, rule, create_workbook):
        """列レンジが重ならないテーブル間の空行も違反として報告される。

        ユーザ方針: 「本質的に1テーブルかどうかと空行があるかは別問題」「空行置くなよ」
        """
        sheets_data = {
            "Sheet1": [
                ["名前", "年齢", None, None, None],
                ["太郎", 20, None, None, None],
                ["花子", 25, None, None, None],
                [None, None, None, None, None],  # 空行（行4）
                [None, None, None, None, None],  # 空行（行5）
                [None, None, None, "商品", "価格"],
                [None, None, None, "りんご", 100],
            ]
        }
        first = _make_region(1, 3, 1, 2)
        second = _make_region(6, 7, 4, 5)
        ctx = self._ctx_with_two_tables(create_workbook, sheets_data, first, second)

        result = rule.check(ctx)
        assert result.passed is False
        assert any("テーブル間" in v.description and "行4" in v.cell_range for v in result.violations)
        assert any("テーブル間" in v.description and "行5" in v.cell_range for v in result.violations)

    def test_inter_table_non_empty_gap_not_flagged(self, rule, create_workbook):
        """テーブル間に値のある行（例: タイトル）がある場合、その行は空行ではないため違反にしない。"""
        sheets_data = {
            "Sheet1": [
                ["名前", "年齢"],
                ["太郎", 20],
                ["花子", 25],
                ["セクション B", None],  # 値あり（行4）
                [None, None],  # 空行（行5）
                ["名前", "年齢"],
                ["次郎", 30],
            ]
        }
        first = _make_region(1, 3, 1, 2)
        second = _make_region(6, 7, 1, 2)
        ctx = self._ctx_with_two_tables(create_workbook, sheets_data, first, second)

        result = rule.check(ctx)
        # 行4 はテーブル間違反として報告しない / 行5 は空行として報告
        assert all(not ("テーブル間" in v.description and "行4" in v.cell_range) for v in result.violations)
        assert any("テーブル間" in v.description and "行5" in v.cell_range for v in result.violations)

    def test_single_table_no_inter_table_violation(self, rule, create_workbook):
        """テーブルが 1 つだけならテーブル間検出は走らない。"""
        sheets_data = {
            "Sheet1": [
                ["名前", "年齢"],
                ["太郎", 20],
                ["花子", 25],
            ]
        }
        first = _make_region(1, 3, 1, 2)
        workbook = create_workbook(sheets_data=sheets_data)
        sheet = workbook.sheets[0]
        ctx = TableContext(
            workbook=workbook,
            sheet=sheet,
            table_region=first,
            all_tables=[first],
        )

        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
