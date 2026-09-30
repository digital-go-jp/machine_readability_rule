"""L3-07: 単一ファイル時は判定対象外であることを確認するテスト"""

from harunobu.rules.level3.L3_07_format_consistency import FormatConsistencyRule


class TestFormatConsistencyCheck:
    """L3-07 単一ファイルチェック（判定対象外）"""

    def test_check_returns_skipped(self, create_context):
        """単一ファイル時は confidence=0（判定対象外）を返す"""
        ctx = create_context({"Sheet1": [["名前", "値"], ["A市", 100]]})
        result = FormatConsistencyRule().check(ctx)
        assert result.confidence == 0

    def test_check_returns_passed_true(self, create_context):
        """判定対象外でも passed=True を返す"""
        ctx = create_context({"Sheet1": [["名前", "値"], ["A市", 100]]})
        result = FormatConsistencyRule().check(ctx)
        assert result.passed is True

    def test_check_has_no_violations(self, create_context):
        """判定対象外では violations が空"""
        ctx = create_context({"Sheet1": [["名前", "値"], ["A市", 100]]})
        result = FormatConsistencyRule().check(ctx)
        assert result.violations == []
