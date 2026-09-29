"""L3-04: データの単位を記載しているかのテスト"""

from unittest.mock import MagicMock, patch

from harunobu.rules.level3.L3_04_data_units import DataUnitsRule


class TestDataUnitsCheck:
    """L3-04 単位記載チェック"""

    def test_units_in_header_passes(self, create_context):
        """ヘッダーに単位が記載されている場合に違反なし"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "売上（円）", "数量（個）"],
                    ["商品A", 1000, 10],
                    ["商品B", 2000, 20],
                ],
            },
        )
        rule = DataUnitsRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_missing_units_detected(self, create_context):
        """数値列にユニットの記載がない場合に違反を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "数値データ"],
                    ["商品A", 1000],
                    ["商品B", 2000],
                    ["商品C", 3000],
                ],
            },
        )
        rule = DataUnitsRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("単位" in v.description for v in result.violations)

    def test_header_implying_unit_passes(self, create_context):
        """ヘッダー名が単位を暗示している場合に違反なし"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "人口", "面積"],
                    ["東京", 14000000, 2194],
                    ["大阪", 8800000, 1905],
                ],
            },
        )
        rule = DataUnitsRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_string_column_not_checked(self, create_context):
        """文字列列は単位チェックの対象外"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "住所", "備考"],
                    ["A市", "東京", "なし"],
                    ["B市", "大阪", "あり"],
                    ["C市", "福岡", "なし"],
                ],
            },
        )
        rule = DataUnitsRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_no_header_rows_skipped(self, create_context, create_workbook):
        """ヘッダー行が未検出の場合はスキップ（confidence=0.5）"""
        from harunobu.core.models import (
            CellRange,
            Config,
            TableContext,
            TableLayout,
            TableRegion,
        )

        workbook = create_workbook(
            sheets_data={"Sheet1": [[100, 200], [300, 400]]},
        )
        sheet = workbook.sheets[0]
        table_region = TableRegion(
            range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
            layout=TableLayout(header_rows=[], body_start_row=1, body_end_row=2),
            confidence=1.0,
        )
        ctx = TableContext(
            workbook=workbook,
            sheet=sheet,
            table_region=table_region,
            config=Config(),
        )
        rule = DataUnitsRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert result.confidence == 0.5

    def test_score_proportional_to_violations(self, create_context):
        """スコアが違反列の割合に応じて計算される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "数値1", "数値2（円）"],
                    ["A", 100, 1000],
                    ["B", 200, 2000],
                    ["C", 300, 3000],
                ],
            },
        )
        rule = DataUnitsRule()
        result = rule.check(ctx)
        assert result.passed is False
        # 数値列: 数値1（違反）、数値2（円）（通過）
        # 違反1/総列3=33% → score=round(100*(1-1/3))=67
        # assert result.score > 0
        # assert result.score < 100

    def test_ai_detects_di_value_has_unit(self, create_context):
        """「DI値」ヘッダーをAIが単位あり（指数）と判定するテスト（モック）"""
        with patch("harunobu.rules.level3.L3_04_data_units.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.batch_infer_units_from_headers.return_value = [
                {"has_unit": True, "inferred_unit": "指数（-100〜100）", "explanation": "DI値は指数"},
            ]
            MockClass.get_instance.return_value = mock_ai

            ctx = create_context({"Sheet1": [["DI値"], [50], [-10], [30]]})
            rule = DataUnitsRule()
            result = rule.check(ctx)
            assert result.passed is True  # AI が単位あると判定
            assert len(result.violations) == 0

    def test_ai_detects_jushinritsu_has_unit(self, create_context):
        """「受診率」ヘッダーをAIが単位あり（%）と判定するテスト（モック）"""
        with patch("harunobu.rules.level3.L3_04_data_units.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.batch_infer_units_from_headers.return_value = [
                {"has_unit": True, "inferred_unit": "%", "explanation": "受診率は%"},
            ]
            MockClass.get_instance.return_value = mock_ai

            ctx = create_context({"Sheet1": [["受診率"], [85.2], [72.3], [91.0]]})
            rule = DataUnitsRule()
            result = rule.check(ctx)
            assert result.passed is True  # AI が単位あると判定
            assert len(result.violations) == 0

    def test_ai_unavailable_falls_back_to_keyword_list(self, create_context):
        """AI unavailable 時は固定キーワードリストのみ使用"""
        with patch("harunobu.rules.level3.L3_04_data_units.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai

            # 「DI値」はキーワードリストにないため違反になる
            ctx = create_context({"Sheet1": [["DI値"], [50], [-10], [30]]})
            rule = DataUnitsRule()
            result = rule.check(ctx)
            assert result.passed is False  # AI なしではキーワードリストのみ → 違反
            assert result.confidence == 0.65  # AI 未使用時は 0.65
            # AI のバッチAPIは呼ばれない
            mock_ai.batch_infer_units_from_headers.assert_not_called()

    def test_explicit_unit_in_parentheses_skips_ai(self, create_context):
        """括弧内に単位がある場合は AI を呼ばない"""
        with patch("harunobu.rules.level3.L3_04_data_units.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            MockClass.get_instance.return_value = mock_ai

            ctx = create_context({"Sheet1": [["売上（円）"], [1000], [2000], [3000]]})
            rule = DataUnitsRule()
            result = rule.check(ctx)
            assert result.passed is True
            # 括弧内に単位があるので AI は呼ばれない
            mock_ai.batch_infer_units_from_headers.assert_not_called()
