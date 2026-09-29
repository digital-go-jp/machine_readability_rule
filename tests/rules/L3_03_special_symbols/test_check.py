"""L3-03: 特殊記号の定義を明記しているかのテスト"""

from harunobu.rules.level3.L3_03_special_symbols import SpecialSymbolsRule


class TestSpecialSymbolsCheck:
    """L3-03 は現在判定対象外（confidence=0）"""

    def test_always_returns_confidence_zero(self, create_context):
        ctx = create_context(
            {"Sheet1": [["名前", "値"], ["A市", "-"], ["B市", "x"]]},
        )
        result = SpecialSymbolsRule().check(ctx)
        assert result.confidence == 0
        assert result.passed is True
        assert result.violations == []
