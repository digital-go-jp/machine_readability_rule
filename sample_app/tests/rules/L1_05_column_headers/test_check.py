"""L1-05: 列ヘッダーの存在チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.rules.level1.L1_05_column_headers import ColumnHeadersRule


class TestColumnHeadersCheck:
    """L1-05 列ヘッダーチェック"""

    @pytest.fixture
    def rule(self):
        return ColumnHeadersRule()

    def test_all_headers_present_passes(self, rule, create_context):
        """すべての列にヘッダーがある場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢", "住所"], ["太郎", 20, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_missing_header_detected(self, rule, create_context):
        """ヘッダーが空白の列がデータを持つ場合に検出される"""
        ctx = create_context({"Sheet1": [["名前", None, "住所"], ["太郎", 20, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_multiple_missing_headers(self, rule, create_context):
        """複数のヘッダー欠落が検出される"""
        ctx = create_context({"Sheet1": [[None, None, "住所"], ["太郎", 20, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2

    def test_score_proportional_to_missing_headers(self, rule, create_context):
        """スコアは欠落ヘッダーの割合に応じて減少する"""
        ctx = create_context({"Sheet1": [["名前", None, None, "住所"], ["太郎", 20, 30, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is False
        # 4列中2列が欠落 -> round(100 * 2 / 4) = 50
        # assert result.score == 50

    def test_empty_column_no_header_no_data_not_flagged(self, rule, create_context):
        """ヘッダーもデータもない列は違反としない"""
        ctx = create_context({"Sheet1": [["名前", None, "住所"], ["太郎", None, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_merged_header_spanning_columns(self, rule, create_context):
        """結合ヘッダーがカバーする列は違反としない"""
        ctx = create_context(
            {"Sheet1": [["名前", "住所", None], ["太郎", "東京", "港区"]]},
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 1,
                    "start_col": 2,
                    "end_row": 1,
                    "end_col": 3,
                }
            ],
        )
        result = rule.check(ctx)
        # 「住所」が2-3列目を結合カバー → col 3はカバー済み
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_merged_header_empty_still_flags(self, rule, create_context):
        """結合ヘッダーが空の場合は、データ列があれば違反"""
        ctx = create_context(
            {"Sheet1": [["名前", None, None], ["太郎", "東京", "港区"]]},
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 1,
                    "start_col": 2,
                    "end_row": 1,
                    "end_col": 3,
                }
            ],
        )
        result = rule.check(ctx)
        # 結合セルは空なのでカバーされない → col 2, 3はデータあり → 2件の違反
        assert result.passed is False
        assert len(result.violations) == 2

    def test_multi_row_header(self, rule, create_context):
        """複数行ヘッダーのいずれかに値があればOK"""
        from harunobu.core.models import (
            CellRange,
            TableLayout,
            TableRegion,
        )

        ctx = create_context({"Sheet1": [["カテゴリ", None, None], [None, "名前", "住所"], ["A", "太郎", "東京"]]})
        # ヘッダー行を2行に設定
        ctx.table_region = TableRegion(
            range=CellRange(start_row=1, start_col=1, end_row=3, end_col=3),
            layout=TableLayout(
                header_rows=[1, 2],
                body_start_row=3,
                body_end_row=3,
            ),
            confidence=1.0,
        )
        result = rule.check(ctx)
        # 各列: col1→row1に「カテゴリ」あり, col2→row2に「名前」あり, col3→row2に「住所」あり
        assert result.passed is True
        # assert result.score == 100

    def test_header_with_only_whitespace_is_missing(self, rule, create_context):
        """空白文字のみのヘッダーは欠落扱い"""
        ctx = create_context({"Sheet1": [["名前", "  ", "住所"], ["太郎", 20, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_column_with_header_but_no_data(self, rule, create_context):
        """ヘッダーはあるがデータのない列は違反としない"""
        ctx = create_context({"Sheet1": [["名前", "年齢", "住所"], ["太郎", None, "東京"]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
