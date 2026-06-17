"""L1-09: 空白とゼロの区別チェックのテスト"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from harunobu.rules.level1.L1_09_blank_vs_zero import BlankVsZeroRule

_MODULE = "harunobu.rules.level1.L1_09_blank_vs_zero.AISemanticChecker"


def _mock_checker(is_available: bool, ai_results: list | None = None):
    mock = MagicMock()
    mock.is_available.return_value = is_available
    if ai_results is not None:
        mock.batch_check_zero_unlikely_columns.return_value = ai_results
    return mock


class TestBlankVsZeroCheck:
    def test_ai_off_returns_confidence_zero(self, create_context):
        """AI 利用不可のとき confidence=0、passed=True を返す。"""
        with patch(_MODULE) as MockClass:
            MockClass.get_instance.return_value = _mock_checker(is_available=False)
            ctx = create_context({"Sheet1": [["名前", "人口"], ["A市", 0], ["B市", None], ["C市", 1000], ["D市", 0]]})
            result = BlankVsZeroRule().check(ctx)
        assert result.confidence == 0
        assert result.passed is True
        assert result.violations == []

    def test_too_few_rows_returns_confidence_zero(self, create_context):
        """データ行数 < 3 → confidence=0"""
        with patch(_MODULE) as MockClass:
            MockClass.get_instance.return_value = _mock_checker(is_available=True)
            ctx = create_context({"Sheet1": [["名前", "人口"], ["A市", 0], ["B市", None]]})
            result = BlankVsZeroRule().check(ctx)
        assert result.confidence == 0
        assert result.passed is True

    def test_no_ambiguous_columns_passes(self, create_context):
        """空白・ゼロ混在列なし → confidence=0.8, passed=True"""
        with patch(_MODULE) as MockClass:
            MockClass.get_instance.return_value = _mock_checker(is_available=True)
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "人口"],
                        ["A市", 1000],
                        ["B市", 2000],
                        ["C市", 3000],
                    ]
                }
            )
            result = BlankVsZeroRule().check(ctx)
        assert result.confidence == 0.8
        assert result.passed is True
        assert result.violations == []

    def test_zero_unlikely_column_detected(self, create_context):
        """AI が zero_unlikely=True かつ confidence≥0.7 → Warning 違反あり"""
        with patch(_MODULE) as MockClass:
            MockClass.get_instance.return_value = _mock_checker(
                is_available=True,
                ai_results=[{"zero_unlikely": True, "reason": "人口はゼロにならない", "confidence": 0.9}],
            )
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "人口"],
                        ["A市", 0],
                        ["B市", None],
                        ["C市", 1000],
                        ["D市", 0],
                    ]
                }
            )
            result = BlankVsZeroRule().check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.confidence == 0.8
        assert "人口" in result.violations[0].description

    def test_zero_likely_column_passes(self, create_context):
        """AI が zero_unlikely=False → 違反なし"""
        with patch(_MODULE) as MockClass:
            MockClass.get_instance.return_value = _mock_checker(
                is_available=True,
                ai_results=[{"zero_unlikely": False, "reason": "変化率はゼロが正常", "confidence": 0.9}],
            )
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "変化率"],
                        ["A市", 0],
                        ["B市", None],
                        ["C市", 5.0],
                        ["D市", 0],
                    ]
                }
            )
            result = BlankVsZeroRule().check(ctx)
        assert result.passed is True
        assert result.violations == []
        assert result.confidence == 0.8

    def test_confidence_below_threshold_passes(self, create_context):
        """zero_unlikely=True でも AI confidence < 0.7 → 違反なし"""
        with patch(_MODULE) as MockClass:
            MockClass.get_instance.return_value = _mock_checker(
                is_available=True,
                ai_results=[{"zero_unlikely": True, "reason": "不明", "confidence": 0.5}],
            )
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "件数"],
                        ["A市", 0],
                        ["B市", None],
                        ["C市", 10],
                        ["D市", 0],
                    ]
                }
            )
            result = BlankVsZeroRule().check(ctx)
        assert result.passed is True
        assert result.violations == []

    def test_ai_api_failure_returns_confidence_zero(self, create_context):
        """AI API 呼び出し失敗（None 返却）→ confidence=0"""
        with patch(_MODULE) as MockClass:
            mock = _mock_checker(is_available=True)
            mock.batch_check_zero_unlikely_columns.return_value = None
            MockClass.get_instance.return_value = mock
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "人口"],
                        ["A市", 0],
                        ["B市", None],
                        ["C市", 1000],
                        ["D市", 0],
                    ]
                }
            )
            result = BlankVsZeroRule().check(ctx)
        assert result.confidence == 0
        assert result.passed is True
        assert result.violations == []
