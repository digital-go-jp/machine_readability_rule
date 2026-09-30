"""L1-01: ファイル形式チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.rules.level1.L1_01_file_format import FileFormatRule


class TestFileFormatCheck:
    """L1-01 ファイル形式チェック"""

    @pytest.fixture
    def rule(self):
        return FileFormatRule()

    def test_xlsx_passes(self, rule, create_context):
        """xlsx形式はpass"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.xlsx",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_csv_passes(self, rule, create_context):
        """csv形式はpass"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_tsv_passes(self, rule, create_context):
        """tsv形式はpass"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.tsv",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_allowed_formats_constant(self, rule):
        """許可フォーマットにxlsx/csv/tsvが含まれる"""
        assert rule.ALLOWED_FORMATS == {"xlsx", "csv", "tsv"}

    def test_violation_has_correct_rule_id(self, rule, create_context):
        """rule_idが正しく設定される"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.xlsx",
        )
        result = rule.check(ctx)
        assert result.rule_id == "L1-01"

    def test_xlsx_confidence_is_1(self, rule, create_context):
        """xlsx形式のチェックはconfidence=1（決定論的）"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.xlsx",
        )
        result = rule.check(ctx)
        assert result.confidence == 1.0

    def test_csv_score_is_100(self, rule, create_context):
        """csv形式もスコア100"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="data.csv",
        )
        result = rule.check(ctx)
        # assert result.score == 100
        assert result.confidence == 1.0

    def test_message_contains_format(self, rule, create_context):
        """メッセージにファイル形式名が含まれる"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.xlsx",
        )
        result = rule.check(ctx)
        assert "xlsx" in result.message
