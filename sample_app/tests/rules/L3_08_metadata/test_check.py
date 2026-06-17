"""L3-08: データの定義や更新履歴が記載されているかのテスト"""

from harunobu.rules.level3.L3_08_metadata import MetadataRule


class TestMetadataCheck:
    """L3-08 は現在判定対象外（confidence=0）"""

    def test_always_returns_confidence_zero(self, create_context):
        ctx = create_context(
            {"Sheet1": [["名前", "値"], ["A市", 100], ["B市", 200]]},
        )
        result = MetadataRule().check(ctx)
        assert result.confidence == 0
        assert result.passed is True
        assert result.violations == []
