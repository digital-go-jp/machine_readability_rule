"""L2-01: AIセマンティックチェック統合のテスト"""

from unittest.mock import MagicMock, patch

from harunobu.rules.level2.L2_01_numeric_purity import NumericPurityRule


class TestNumericPurityAICheck:
    """L2-01 AI統合チェック"""

    def test_ai_not_called_for_deterministically_detected_cells(self, create_context):
        """決定論的に検出済みのセルはAIに渡されない"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_unit_in_cells.return_value = []
        with patch("harunobu.rules.level2.L2_01_numeric_purity.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            # "約1,200名" は検出レイヤーの単純化により決定論的に捕捉される
            ctx = create_context(
                {
                    "Sheet1": [
                        ["項目", "値"],
                        ["A", "約1,200名"],
                        ["B", 200],
                        ["C", 300],
                    ]
                }
            )
            rule = NumericPurityRule()
            result = rule.check(ctx)
            # 決定論的チェックで違反が検出されている
            assert result.passed is False
            assert len(result.violations) == 1
            assert "AI検出" not in result.violations[0].description
            # AIのバッチ呼び出しは行われないか空リストで呼ばれる
            # （決定論的に検出済みのため AI 候補が存在しない）
            if mock_ai.batch_check_unit_in_cells.called:
                args = mock_ai.batch_check_unit_in_cells.call_args[0][0]
                assert len(args) == 0

    def test_ai_unavailable_fallback(self, create_context):
        """AI unavailable 時も既存の決定論的チェックが動作する"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        with patch("harunobu.rules.level2.L2_01_numeric_purity.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["項目", "値"],
                        ["A", "200円"],
                        ["B", 400],
                        ["C", 600],
                    ]
                }
            )
            rule = NumericPurityRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert any("単位" in v.description for v in result.violations)
            # AI unavailable 時は confidence が 0.85
            assert result.confidence == 0.85

    def test_ai_available_higher_confidence(self, create_context):
        """AI利用可能時はconfidenceが上がる"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_unit_in_cells.return_value = []
        with patch("harunobu.rules.level2.L2_01_numeric_purity.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context({"Sheet1": [["項目", "値"], [100, 200], [300, 400]]})
            rule = NumericPurityRule()
            result = rule.check(ctx)
            assert result.confidence == 0.90

    def test_ai_low_confidence_ignored(self, create_context):
        """AIの確信度が低い場合は違反として追加しない"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_unit_in_cells.return_value = [
            {
                "has_unit": True,
                "numeric_part": "100",
                "unit_part": "個",
                "confidence": 0.3,  # 閾値(0.7)未満
            }
        ]
        with patch("harunobu.rules.level2.L2_01_numeric_purity.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["項目", "値"],
                        ["A", "100個くらい"],
                        ["B", 200],
                        ["C", 300],
                    ]
                }
            )
            rule = NumericPurityRule()
            result = rule.check(ctx)
            ai_violations = [v for v in result.violations if "AI検出" in v.description]
            assert len(ai_violations) == 0

    def test_ai_does_not_duplicate_deterministic(self, create_context):
        """AIが決定論的チェックで既に検出済みのセルを重複追加しない"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        # バッチ結果は空（"200円" は決定論的に検出済みでAI候補に含まれない）
        mock_ai.batch_check_unit_in_cells.return_value = []
        with patch("harunobu.rules.level2.L2_01_numeric_purity.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["項目", "値"],
                        ["A", "200円"],
                        ["B", 400],
                        ["C", 600],
                    ]
                }
            )
            rule = NumericPurityRule()
            result = rule.check(ctx)
            # "200円" は決定論的に1件検出。AIで重複しない
            unit_violations = [v for v in result.violations if "単位" in v.description]
            assert len(unit_violations) == 1
