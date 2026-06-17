"""L1-04: データ範囲外の無関係情報チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.core.models import (
    CellRange,
    Config,
    OtherCell,
    TableContext,
    TableLayout,
    TableRegion,
)
from harunobu.rules.level1.L1_04_irrelevant_info import IrrelevantInfoRule


class TestIrrelevantInfoCheck:
    """L1-04 データ範囲外情報チェック（厳しめポリシー: sheet_others が非空なら NG）"""

    @pytest.fixture
    def rule(self):
        return IrrelevantInfoRule()

    def _make_context(self, create_workbook, sheets_data, sheet_others):
        """sheet_others を注入した TableContext を生成"""
        wb = create_workbook(sheets_data=sheets_data)
        sheet = wb.sheets[0]
        table_region = TableRegion(
            range=CellRange(
                start_row=1,
                start_col=1,
                end_row=sheet.max_row,
                end_col=sheet.max_col,
            ),
            layout=TableLayout(
                header_rows=[1],
                body_start_row=2,
                body_end_row=sheet.max_row,
            ),
            confidence=1.0,
        )
        return TableContext(
            workbook=wb,
            sheet=sheet,
            table_region=table_region,
            config=Config(),
            sheet_others=sheet_others,
        )

    def test_no_irrelevant_info_passes(self, rule, create_context):
        """sheet_others が空なら pass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_title_above_table_is_flagged(self, rule, create_workbook):
        """テーブル上方のタイトル行は厳しめポリシーで違反扱い"""
        ctx = self._make_context(
            create_workbook,
            {"Sheet1": [["人口統計表", None], ["名前", "年齢"], ["太郎", 20]]},
            sheet_others=[
                OtherCell(row=1, col=1, value="人口統計表", region_type="title"),
            ],
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "title" in result.violations[0].description

    def test_note_below_table_is_flagged(self, rule, create_workbook):
        """テーブル下方の注釈行は厳しめポリシーで違反扱い"""
        ctx = self._make_context(
            create_workbook,
            {"Sheet1": [["名前", "年齢"], ["太郎", 20], ["※出典: 総務省", None]]},
            sheet_others=[
                OtherCell(row=3, col=1, value="※出典: 総務省", region_type="note"),
            ],
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "note" in result.violations[0].description

    def test_title_and_footer_both_flagged(self, rule, create_workbook):
        """タイトル行と注釈行の両方がある場合はそれぞれ違反としてカウントされる"""
        ctx = self._make_context(
            create_workbook,
            {
                "Sheet1": [
                    ["人口統計表", None],
                    ["令和5年度", None],
                    ["名前", "年齢"],
                    ["太郎", 20],
                    ["※出典: 総務省", None],
                    ["作成日: 2024/01/01", None],
                ]
            },
            sheet_others=[
                OtherCell(row=1, col=1, value="人口統計表", region_type="title"),
                OtherCell(row=2, col=1, value="令和5年度", region_type="title"),
                OtherCell(row=5, col=1, value="※出典: 総務省", region_type="source"),
                OtherCell(row=6, col=1, value="作成日: 2024/01/01", region_type="note"),
            ],
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 4

    def test_sheet_others_one_cell_one_violation(self, rule, create_workbook):
        """OtherCell ごとに 1 Violation"""
        wb = create_workbook(sheets_data={"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        sheet = wb.sheets[0]
        table_region = TableRegion(
            range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
            layout=TableLayout(
                header_rows=[1],
                body_start_row=2,
                body_end_row=2,
            ),
            confidence=1.0,
        )
        ctx = TableContext(
            workbook=wb,
            sheet=sheet,
            table_region=table_region,
            config=Config(),
            sheet_others=[
                OtherCell(row=1, col=5, value="注記", region_type="note"),
                OtherCell(row=3, col=1, value="出典", region_type="source"),
            ],
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2
        assert all("others" in v.description for v in result.violations)
