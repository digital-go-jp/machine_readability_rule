"""L1-13: 非表示行・列チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.rules.level1.L1_13_hidden_rows_columns import HiddenRowsColumnsRule


class TestHiddenRowsColumnsCheck:
    """L1-13 非表示行・列チェック"""

    @pytest.fixture
    def rule(self):
        return HiddenRowsColumnsRule()

    def test_no_hidden_rows_or_cols_passes(self, rule, create_context):
        """非表示行・列がない場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_hidden_row_in_table_region_fails(self, rule, create_context):
        """table_region内の非表示行は違反"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]},
            hidden_rows={"Sheet1": [2]},
        )
        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 95
        assert len(result.violations) == 1
        assert result.violations[0].cell_range == "行2"
        assert "シート使用範囲内" in result.violations[0].description

    def test_hidden_col_in_table_region_fails(self, rule, create_context):
        """table_region内の非表示列は違反"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢", "住所"], ["太郎", 20, "東京"]]},
            hidden_cols={"Sheet1": [3]},
        )
        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 95
        assert len(result.violations) == 1
        assert result.violations[0].cell_range == "列3"

    def test_hidden_row_outside_table_region_but_in_used_range_fails(self, rule, create_context):
        """table_region外でも使用範囲内の非表示行は違反"""
        ctx = create_context({"Sheet1": [["A", "B"], ["1", "2"], ["3", "4"]]})
        ctx.sheet.hidden_rows = [3]
        ctx.table_region.range.end_row = 2

        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 95
        assert result.violations[0].cell_range == "行3"

    def test_hidden_col_outside_table_region_but_in_used_range_fails(self, rule, create_context):
        """table_region外でも使用範囲内の非表示列は違反"""
        ctx = create_context({"Sheet1": [["A", "B", "C"], ["1", "2", "3"]]})
        ctx.sheet.hidden_cols = [3]
        ctx.table_region.range.end_col = 2

        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 95
        assert result.violations[0].cell_range == "列3"

    def test_hidden_rows_and_cols_outside_used_range_are_ignored(self, rule, create_context):
        """使用範囲外の非表示行・列は無視する"""
        ctx = create_context({"Sheet1": [["A", "B"], ["1", "2"]]})
        ctx.sheet.hidden_rows = [3]
        ctx.sheet.hidden_cols = [3]

        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_consecutive_hidden_rows_and_cols_are_grouped(self, rule, create_context):
        """連続する非表示行・列は範囲として報告される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["A", "B", "C"],
                    ["1", "2", "3"],
                    ["4", "5", "6"],
                ]
            },
            hidden_rows={"Sheet1": [2, 3]},
            hidden_cols={"Sheet1": [1, 2]},
        )
        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 80
        assert [v.cell_range for v in result.violations] == ["行2-3", "列1-2"]

    def test_hidden_rows_on_other_sheet_do_not_affect_current_sheet(self, rule, create_context):
        """別シートの非表示行は対象シートに影響しない"""
        ctx = create_context(
            {
                "Sheet1": [["A", "B"], ["1", "2"]],
                "Sheet2": [["C", "D"], ["3", "4"]],
            },
            hidden_rows={"Sheet2": [1]},
            sheet_index=0,
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_hidden_rows_on_selected_second_sheet_fails(self, rule, create_context):
        """対象シートの非表示行は違反"""
        ctx = create_context(
            {
                "Sheet1": [["A", "B"], ["1", "2"]],
                "Sheet2": [["C", "D"], ["3", "4"]],
            },
            hidden_rows={"Sheet2": [1]},
            sheet_index=1,
        )
        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 95
        assert result.violations[0].sheet == "Sheet2"
        assert result.violations[0].cell_range == "行1"

    def test_csv_is_skipped(self, rule, create_context):
        """CSVはチェック対象外"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.csv",
            hidden_rows={"Sheet1": [2]},
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0
