"""L1-11: 書式によるデータ区別チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.core.models import CellFormat
from harunobu.rules.level1.L1_11_format_based_semantics import (
    FormatBasedSemanticsRule,
)


class TestFormatBasedSemanticsCheck:
    """L1-11 書式依存データ区別チェック"""

    @pytest.fixture
    def rule(self):
        return FormatBasedSemanticsRule()

    def test_no_format_issues_passes(self, rule, create_context):
        """書式の区別がない場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_csv_skipped(self, rule, create_context):
        """CSV形式の場合はチェック対象外"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True

    def test_varied_font_colors_detected(self, rule, create_context):
        """列内でフォント色が複数使われている場合は違反"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["ステータス", "値"],
                    ["正常", 100],
                    ["異常", 50],
                    ["正常", 80],
                ]
            }
        )
        # body行のセルにフォント色を設定
        ctx.sheet.cells[(2, 1)].fmt = CellFormat(font_color="000000")
        ctx.sheet.cells[(3, 1)].fmt = CellFormat(font_color="FF0000")  # 赤
        ctx.sheet.cells[(4, 1)].fmt = CellFormat(font_color="000000")
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) >= 1

    def test_partial_bold_detected(self, rule, create_context):
        """一部のセルのみ太字の場合は違反"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "点数"],
                    ["太郎", 100],
                    ["花子", 50],
                    ["次郎", 80],
                ]
            }
        )
        # 1セルだけ太字
        ctx.sheet.cells[(2, 2)].fmt = CellFormat(bold=True)
        result = rule.check(ctx)
        assert result.passed is False
        assert any("太字" in v.description for v in result.violations)

    def test_partial_italic_detected(self, rule, create_context):
        """一部のセルのみ斜体の場合は違反"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "点数"],
                    ["太郎", 100],
                    ["花子", 50],
                    ["次郎", 80],
                ]
            }
        )
        ctx.sheet.cells[(3, 2)].fmt = CellFormat(italic=True)
        result = rule.check(ctx)
        assert result.passed is False
        assert any("斜体" in v.description for v in result.violations)

    def test_varied_bg_colors_detected(self, rule, create_context):
        """背景色が複数の非デフォルト色で使用されている場合は違反"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["ステータス", "値"],
                    ["正常", 100],
                    ["異常", 50],
                    ["警告", 80],
                ]
            }
        )
        ctx.sheet.cells[(2, 1)].fmt = CellFormat(bg_color="00FF00")  # 緑
        ctx.sheet.cells[(3, 1)].fmt = CellFormat(bg_color="FF0000")  # 赤
        ctx.sheet.cells[(4, 1)].fmt = CellFormat(bg_color="FFFF00")  # 黄
        result = rule.check(ctx)
        assert result.passed is False
        assert any("背景色" in v.description for v in result.violations)

    def test_all_bold_passes(self, rule, create_context):
        """全セルが太字の場合は違反にならない"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "点数"],
                    ["太郎", 100],
                    ["花子", 50],
                ]
            }
        )
        ctx.sheet.cells[(2, 2)].fmt = CellFormat(bold=True)
        ctx.sheet.cells[(3, 2)].fmt = CellFormat(bold=True)
        result = rule.check(ctx)
        # 全セル太字 → bold_count == total_cells → 違反なし
        assert not any("太字" in v.description for v in result.violations)

    def test_single_cell_column_skipped(self, rule, create_context):
        """データが1セルのみの列はチェック対象外"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "値"],
                    ["太郎", 100],
                ]
            }
        )
        ctx.sheet.cells[(2, 1)].fmt = CellFormat(font_color="FF0000")
        result = rule.check(ctx)
        # total_cells < 2 → スキップ
        assert result.passed is True
