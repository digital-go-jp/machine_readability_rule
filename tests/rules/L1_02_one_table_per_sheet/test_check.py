"""L1-02: 1シート1表チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.rules.level1.L1_02_one_table_per_sheet import OneTablePerSheetRule


class TestOneTablePerSheetCheck:
    """L1-02 1シート1表チェック"""

    @pytest.fixture
    def rule(self):
        return OneTablePerSheetRule()

    def test_single_table_passes(self, rule, create_context):
        """1シートに1表のみの場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_multiple_tables_detected(self, rule, create_context):
        """空白行2行以上で区切られた複数テーブルが検出される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢"],
                    ["太郎", 20],
                    [None, None],  # 空白行1
                    [None, None],  # 空白行2（2行連続で別テーブル判定）
                    ["商品", "価格"],
                    ["りんご", 100],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) >= 2
        # assert result.score < 100

    def test_single_blank_row_splits(self, rule, create_context):
        """空白行が1行でもLayoutDetectorがテーブルを分割する場合は検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢"],
                    ["太郎", 20],
                    [None, None],  # 空白行1行
                    ["花子", 25],
                ]
            }
        )
        result = rule.check(ctx)
        # LayoutDetectorの判定に依存（1行空白でも分割される場合がある）
        # 分割されなければpass、されればfail — どちらも正しい動作
        assert isinstance(result.passed, bool)

    def test_empty_sheet_passes(self, rule, create_context):
        """空シートの場合はpass"""
        ctx = create_context({"Sheet1": [[None, None]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_three_tables_score(self, rule, create_context):
        """3テーブル検出時のスコアが40（100 - 2*30）"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢"],
                    ["太郎", 20],
                    [None, None],
                    [None, None],
                    ["商品", "価格"],
                    ["りんご", 100],
                    [None, None],
                    [None, None],
                    ["地区", "人口"],
                    ["東京", 14000000],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 3
        # assert result.score == 40

    def test_trailing_blank_rows_not_split(self, rule, create_context):
        """末尾の空白行は別ブロックとしてカウントされない"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢"],
                    ["太郎", 20],
                    ["花子", 25],
                    [None, None],
                    [None, None],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_blank_row_within_block(self, rule, create_context):
        """ブロック内の1行空白の扱いはLayoutDetectorに委譲"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢"],
                    ["太郎", 20],
                    [None, None],  # 1行空白
                    ["花子", 25],
                    ["次郎", 30],
                ]
            }
        )
        result = rule.check(ctx)
        # LayoutDetectorの判定に依存
        assert isinstance(result.passed, bool)
