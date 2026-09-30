"""L3-06: 地域コード又は地域名称が表記されているかのテスト"""

from unittest.mock import MagicMock, patch

from harunobu.rules.level3.L3_06_region_code import RegionCodeRule


class TestRegionCodeCheck:
    """L3-06 地域コード/名称チェック"""

    def test_no_region_data_passes(self, create_context):
        """地域データが含まれない場合に違反なし"""
        ctx = create_context(
            {"Sheet1": [["商品", "価格"], ["りんご", 100], ["みかん", 200]]},
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_abbreviated_prefecture_detected(self, create_context):
        """都道府県名が省略されている場合に違反を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["都道府県", "人口"],
                    ["東京", 14000000],
                    ["大阪", 8800000],
                    ["愛知", 7500000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("省略" in v.description for v in result.violations)

    def test_full_prefecture_name_passes(self, create_context):
        """正式な都道府県名が使用されている場合"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["都道府県", "地域コード", "人口"],
                    ["東京都", "13", 14000000],
                    ["大阪府", "27", 8800000],
                    ["愛知県", "23", 7500000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        # コード列もあるので省略違反はない
        assert all("省略" not in v.description for v in result.violations)

    def test_municipal_code_column_passes(self, create_context):
        """全国地方公共団体コード（6桁）が含まれる場合はパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["団体コード", "市区町村", "人口"],
                    ["131016", "千代田区", 66000],
                    ["131024", "中央区", 173000],
                    ["131032", "港区", 262000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_prefecture_with_code_passes(self, create_context):
        """都道府県コード列がある場合はコード関連違反なし"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["都道府県コード", "都道府県名", "値"],
                    ["13", "東京都", 100],
                    ["27", "大阪府", 200],
                    ["23", "愛知県", 300],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        # コード列あり → コード表関連の違反なし
        code_violations = [v for v in result.violations if "コード" in v.description and "表" not in v.description]
        assert len(code_violations) == 0

    def test_region_data_detected_without_header_keyword(self, create_context):
        """ヘッダーキーワードがなくても都道府県名がデータに多ければ地域列として検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名称", "人口"],
                    ["東京都", 14000000],
                    ["大阪府", 8800000],
                    ["愛知県", 7500000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        # ヘッダーに「都道府県」などなくても、データが都道府県名なら地域列とみなす
        # 正式名称使用かつコード列なし → "地域コード列が見つかりません" 1件
        assert len(result.violations) <= 1  # 最大1件（地域コード列なし）

    def test_no_header_rows_skipped(self, create_context):
        """ヘッダー行がない場合はスキップ"""
        from harunobu.core.models import TableLayout

        ctx = create_context(
            {"Sheet1": [["東京都", 100], ["大阪府", 200]]},
        )
        ctx.table_region.layout = TableLayout(
            header_rows=[],
            body_start_row=1,
            body_end_row=2,
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert result.confidence == 0.5

    def test_ai_detects_ambiguous_headers(self, create_context):
        """AIが曖昧なヘッダーを検出するテスト"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.assess_column_header_clarity.return_value = [
            {
                "header": "区分",
                "is_ambiguous": True,
                "suggested_improvement": "地域区分",
                "reason": "何の区分か不明",
            }
        ]
        with patch("harunobu.rules.level3.L3_06_region_code.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["都道府県", "地域コード", "区分"],
                        ["東京都", "13", "関東"],
                        ["大阪府", "27", "近畿"],
                    ],
                },
            )
            rule = RegionCodeRule()
            result = rule.check(ctx)
            assert any("AI検出" in v.description for v in result.violations)
            assert result.confidence == 0.80

    def test_ai_unavailable_fallback(self, create_context):
        """AI unavailable 時も既存の決定論的チェックが動作する"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        with patch("harunobu.rules.level3.L3_06_region_code.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["都道府県", "人口"],
                        ["愛知", 7500000],
                        ["岩手", 1200000],
                        ["千葉", 6300000],
                    ],
                },
            )
            rule = RegionCodeRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert any("省略" in v.description for v in result.violations)
            assert result.confidence == 0.70

    def test_ai_no_ambiguous_headers(self, create_context):
        """AIがすべてのヘッダーを明確と判定した場合"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.assess_column_header_clarity.return_value = []
        with patch("harunobu.rules.level3.L3_06_region_code.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["都道府県", "地域コード", "人口"],
                        ["東京都", "13", 14000000],
                        ["大阪府", "27", 8800000],
                    ],
                },
            )
            rule = RegionCodeRule()
            result = rule.check(ctx)
            # AI検出の違反はないが、信頼度は上がる
            assert not any("AI検出" in v.description for v in result.violations)
            assert result.confidence == 0.80
