"""L1-07: 1セル1データチェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.core.models import ColumnSchema
from harunobu.rules.level1.L1_07_one_data_per_cell import OneDataPerCellRule


class TestOneDataPerCellCheck:
    """L1-07 1セル1データチェック"""

    @pytest.fixture
    def rule(self):
        return OneDataPerCellRule()

    def test_single_data_per_cell_passes(self, rule, create_context):
        """各セルに1つのデータのみの場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_newline_in_cell_detected(self, rule, create_context):
        """セル内改行による複数データが検出される"""
        ctx = create_context({"Sheet1": [["名前", "住所"], ["太郎", "東京都\n千代田区"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "改行" in result.violations[0].description

    def test_none_and_empty_ignored(self, rule, create_context):
        """Noneや空値は無視される"""
        ctx = create_context({"Sheet1": [["名前", "値"], [None, ""], ["太郎", 0]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_score_decreases_with_violations(self, rule, create_context):
        """違反数に応じてスコアが減少する"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "住所"],
                    ["太郎", "東京都\n千代田区"],
                    ["花子", "大阪府\n大阪市"],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2
        # 2件の違反 -> 100 - 2*5 = 90
        # assert result.score == 90

    def test_newline_with_empty_second_line_passes(self, rule, create_context):
        """改行後が空白のみのセルは複数データではない"""
        ctx = create_context({"Sheet1": [["名前", "値"], ["太郎", "東京都\n   "]]})
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_tab_character_ignored(self, rule, create_context):
        """タブ文字は複数データの検出対象外"""
        ctx = create_context({"Sheet1": [["名前", "値"], ["太郎", "東京都\t千代田区"]]})
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_multiple_cells_with_newlines(self, rule, create_context):
        """複数セルに改行がある場合に全件検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "住所", "備考"],
                    ["太郎", "東京都\n千代田区", "メモ1\nメモ2"],
                    ["花子", "大阪府", ""],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2

    def test_sample_ng01_comma_and_paren_numbers(self, rule, create_context):
        """MRサンプル NG-01: 数値, 数値（数値）形式"""
        ctx = create_context(
            {
                "S": [
                    ["区分", "値"],
                    ["総計", "1188389, 391445（355943）"],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) >= 1
        assert "カンマ" in result.violations[0].description

    def test_sample_ng02_two_numbers_in_fullwidth_paren(self, rule, create_context):
        """MRサンプル NG-02: セルが「整数（整数）」のみ"""
        ctx = create_context({"S": [["区分", "売上"], ["総計", "391445（355943）"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert "括弧" in result.violations[0].description

    def test_sample_ng03_ideographic_comma_enumeration(self, rule, create_context):
        """MRサンプル NG-03: 読点（、）が2つ以上"""
        val = "373（平成27年度）、434（平成28年度）、549（平成29年度）"
        ctx = create_context({"S": [["項目", "全国"], ["仕入額", val]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert "読点" in result.violations[0].description

    def test_sample_ng05_middle_dot_enumeration(self, rule, create_context):
        """MRサンプル NG-05: 中黒が2つ以上（3項目列挙）"""
        ctx = create_context({"S": [["自治体", "チャネル"], ["A市", "窓口・電話・メール"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert "中黒" in result.violations[0].description

    def test_sample_ng07_comma_between_non_digit_tokens(self, rule, create_context):
        """MRサンプル NG-07: 課名のカンマ列挙"""
        ctx = create_context({"S": [["自治体", "部署"], ["A市", "総務課, 企画課, 財政課"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert "カンマ" in result.violations[0].description

    def test_thousands_separator_single_number_passes(self, rule, create_context):
        """千位区切りの1数値は違反にしない"""
        ctx = create_context({"S": [["金額"], ["1,234,567"]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_digit_comma_skipped_when_column_numeric(self, rule, create_context):
        """numeric 列では数字同士のカンマ検出をスキップ（千位区切り誤検知抑制）"""
        ctx = create_context(
            {
                "S": [
                    ["区分", "値"],
                    ["A", "1188389, 391445（355943）"],
                ]
            },
            column_schemas=[
                ColumnSchema(col_index=1, inferred_type="text"),
                ColumnSchema(col_index=2, inferred_type="numeric"),
            ],
        )
        result = rule.check(ctx)
        assert result.passed is True
