"""L3-02: 回答のコード表が別添されているかのテスト"""

from harunobu.rules.level3.L3_02_code_table import CodeTableRule


class TestCodeTableCheck:
    """L3-02 は現在判定対象外（confidence=0）"""

    def test_always_returns_confidence_zero(self, create_context):
        ctx = create_context(
            {"Sheet1": [["名前", "区分コード", "値"], ["太郎", 1, 100], ["花子", 2, 200]]},
        )
        result = CodeTableRule().check(ctx)
        assert result.confidence == 0
        assert result.passed is True
        assert result.violations == []
