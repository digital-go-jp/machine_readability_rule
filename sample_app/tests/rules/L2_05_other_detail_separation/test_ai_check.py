"""L2-05: AIセマンティックチェック統合のテスト"""

from unittest.mock import MagicMock, patch

from harunobu.rules.level2.L2_05_other_detail_separation import (
    OtherDetailSeparationRule,
)

# _MIN_BODY_ROWS=20 を満たすための基底データ（通常選択肢）
_CHOICES = ["賛成", "反対", "中立"]


def _rows_with_others(n_normal: int, *others: str) -> list[list]:
    """ヘッダー + n_normal 行の通常選択肢 + others の行を返す"""
    rows: list[list] = [["名前", "回答"]]
    for i in range(n_normal):
        rows.append([f"名前{i:02d}", _CHOICES[i % 3]])
    for j, val in enumerate(others):
        rows.append([f"名前{n_normal + j:02d}", val])
    return rows


class TestOtherDetailSeparationAICheck:
    """L2-05 AI統合チェック"""

    def test_ai_detects_mixed_other_detail(self, create_context):
        """統計的検出が届かない単一「その他」値の詳細混在をAIが検出する

        「その他_駐車場利用」が1種類のみ → 条件1（2種類以上）不成立 → 統計的検出なし
        AI が is_mixed=True を返すことで検出される
        """
        ctx = create_context({"Sheet1": _rows_with_others(19, "その他_駐車場利用")})
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_other_detail_mixed.return_value = [
            {
                "is_mixed": True,
                "other_part": "その他",
                "detail_part": "駐車場利用",
                "confidence": 0.9,
            }
        ]
        with patch("harunobu.rules.level2.L2_05_other_detail_separation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            result = OtherDetailSeparationRule().check(ctx)
        assert any("AI検出" in v.description for v in result.violations)

    def test_ai_unavailable_fallback(self, create_context):
        """AI unavailable 時は統計的チェックのみ実行され confidence が 0.80 になる"""
        # 「4. その他」×3件 + 「その他（詳細）」×1件 → 統計的に「その他（詳細）」を検出
        ctx = create_context(
            {
                "Sheet1": _rows_with_others(
                    14, "4. その他", "4. その他", "4. その他", "その他（詳細あり）", "賛成", "反対"
                )
            }
        )
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        with patch("harunobu.rules.level2.L2_05_other_detail_separation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is False
        assert any("その他" in v.description for v in result.violations)
        assert result.confidence == 0.80

    def test_ai_available_higher_confidence(self, create_context):
        """AI利用可能時は confidence が 0.85 になる"""
        # 20行、「その他」なし → 違反なし、AI 利用可能 → confidence=0.85
        rows = [["名前", "回答"]] + [[f"名前{i:02d}", "賛成" if i % 2 == 0 else "反対"] for i in range(20)]
        ctx = create_context({"Sheet1": rows})
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_other_detail_mixed.return_value = []
        with patch("harunobu.rules.level2.L2_05_other_detail_separation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            result = OtherDetailSeparationRule().check(ctx)
        assert result.confidence == 0.85

    def test_ai_low_confidence_ignored(self, create_context):
        """AIの確信度が閾値（0.7）未満の場合は違反として追加しない"""
        # 「その他_何か」1種類のみ → 統計的検出なし、AI が低確信度で返す → 無視
        ctx = create_context({"Sheet1": _rows_with_others(19, "その他_何か")})
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_other_detail_mixed.return_value = [
            {
                "is_mixed": True,
                "other_part": "その他",
                "detail_part": "何か",
                "confidence": 0.3,  # 閾値(0.7)未満
            }
        ]
        with patch("harunobu.rules.level2.L2_05_other_detail_separation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            result = OtherDetailSeparationRule().check(ctx)
        ai_violations = [v for v in result.violations if "AI検出" in v.description]
        assert len(ai_violations) == 0

    def test_ai_does_not_duplicate_deterministic(self, create_context):
        """統計的検出済みのセルは AI バッチから除外され重複しない"""
        # 「4. その他」×3件（フラグなし）+ 「その他（詳細あり）」×1件（統計的に検出）
        # AI バッチは空リストを返す → 重複なし
        ctx = create_context(
            {
                "Sheet1": _rows_with_others(
                    14, "4. その他", "4. その他", "4. その他", "その他（詳細あり）", "賛成", "反対"
                )
            }
        )
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_other_detail_mixed.return_value = []
        with patch("harunobu.rules.level2.L2_05_other_detail_separation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            result = OtherDetailSeparationRule().check(ctx)
        # 統計的に1件検出。AI で重複しない
        other_violations = [v for v in result.violations if "その他" in v.description]
        assert len(other_violations) == 1

    def test_ai_skips_cells_without_other(self, create_context):
        """「その他」を含まないセルでは AI バッチを呼ばない"""
        rows = [["名前", "回答"]] + [[f"名前{i:02d}", "賛成" if i % 2 == 0 else "反対"] for i in range(20)]
        ctx = create_context({"Sheet1": rows})
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.batch_check_other_detail_mixed.return_value = []
        with patch("harunobu.rules.level2.L2_05_other_detail_separation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            OtherDetailSeparationRule().check(ctx)
        mock_ai.batch_check_other_detail_mixed.assert_not_called()
