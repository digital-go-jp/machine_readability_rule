"""L2-04: 選択肢回答が標準化されているかのテスト"""

from unittest.mock import MagicMock, patch

from harunobu.core.models import ColumnSchema
from harunobu.rules.level2.L2_04_choice_standardization import (
    ChoiceStandardizationRule,
    _find_outliers,
    _is_variant_of,
    _normalize,
)

# テストデータ共通: _MIN_BODY_ROWS=20 を満たすため 20 人分の名前を用意する
# 「名前」列は全ユニーク値 → dominant_values 空 → スキップされる
_NAMES = [f"名前{i:02d}" for i in range(20)]


class TestHelperFunctions:
    """ヘルパー関数の単体テスト"""

    def test_normalize_annotation_suffix(self):
        assert _normalize("該当する ※注釈a") == "該当する"

    def test_normalize_fullwidth_parenthesis(self):
        assert _normalize("該当する（詳細）") == "該当する"

    def test_normalize_bracket_as_value_preserved(self):
        # 選択肢自体が括弧で囲まれている場合は除去しない
        assert _normalize("【取組済】") == "【取組済】"

    def test_normalize_fullwidth_number(self):
        assert _normalize("要支援１") == "要支援1"

    def test_normalize_fullwidth_alpha(self):
        assert _normalize("ＡＢＣ") == "ABC"

    def test_normalize_strips_whitespace(self):
        assert _normalize("  はい  ") == "はい"

    def test_find_outliers_returns_low_frequency_values(self):
        # _OUTLIER_MAX_RATIO=0.05: 1/20=0.05 ≤ 0.05 → outlier ✓
        col_values = {"はい": list(range(1, 20)), "いいえ": [20]}
        result = _find_outliers(col_values, total_rows=20)
        assert "いいえ" in result
        assert "はい" not in result

    def test_find_outliers_excludes_values_above_ratio(self):
        # count=2, total=5 → ratio=0.40 > 0.05 → not outlier
        col_values = {"A": [1, 2, 3], "B": [4, 5]}
        result = _find_outliers(col_values, total_rows=5)
        assert "B" not in result

    def test_is_variant_of_annotation_match(self):
        matched, similar = _is_variant_of("該当する ※注釈a", {"該当する": "該当する", "非該当": "非該当"})
        assert matched is True
        assert similar == "該当する"

    def test_is_variant_of_fullwidth_match(self):
        matched, similar = _is_variant_of("要支援１", {"要支援1": "要支援1"})
        assert matched is True
        assert similar == "要支援1"

    def test_is_variant_of_sequence_match(self):
        # "受診済" vs "受診済み": ratio = 6/7 ≈ 0.857 > 0.75
        matched, similar = _is_variant_of("受診済", {"受診済み": "受診済み"})
        assert matched is True

    def test_is_variant_of_no_match(self):
        matched, similar = _is_variant_of("hello", {"はい": "はい", "いいえ": "いいえ"})
        assert matched is False
        assert similar == ""

    def test_is_variant_of_skips_single_char(self):
        # 1文字の文字列は SequenceMatcher を適用しない
        matched, _ = _is_variant_of("A", {"B": "B"})
        assert matched is False


class TestChoiceStandardizationCheck:
    """L2-04 選択肢表記の標準化チェック（統合テスト）"""

    def test_consistent_choices_passes(self, create_context):
        """選択肢の表記が統一されている場合に違反なし"""
        # "はい"×10, "いいえ"×10 → 各10回 > _OUTLIER_MAX_COUNT=2 → outlier なし
        rows = [["名前", "回答"]] + [[f"名前{i:02d}", "はい" if i % 2 == 0 else "いいえ"] for i in range(20)]
        ctx = create_context({"Sheet1": rows})
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_annotation_suffix_detected(self, create_context):
        """注釈サフィックス付き値が表記揺れとして検出される"""
        # "該当する ※注釈a" を正規化すると "該当する" に一致
        # 19 dominant + 1 outlier = 20 rows: ratio=1/20=0.05 ≤ _OUTLIER_MAX_RATIO ✓
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "対象"],
                    *[[name, "該当する"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "該当する ※注釈a"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is False
        assert any("該当する ※注釈a" in v.description for v in result.violations)
        assert all(v.severity == "warning" for v in result.violations)

    def test_fullwidth_number_normalized_detected(self, create_context):
        """全角数字を含む値が表記揺れとして検出される"""
        # NFKC("要支援１") = "要支援1" → dominant "要支援1" に一致
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "介護区分"],
                    *[[name, "要支援1"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "要支援１"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is False
        assert any("要支援１" in v.description for v in result.violations)

    def test_fullwidth_alpha_detected(self, create_context):
        """全角英字を含む値が表記揺れとして検出される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "区分"],
                    *[[name, "ABC"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "ＡＢＣ"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is False
        assert any("ＡＢＣ" in v.description for v in result.violations)

    def test_similar_string_detected(self, create_context):
        """SequenceMatcher で類似する文字列が表記揺れとして検出される"""
        # "受診済" (3文字) vs "受診済み" (4文字): ratio ≈ 0.857 > 0.75
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "状態"],
                    *[[name, "受診済み"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "受診済"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is False
        assert any("受診済" in v.description for v in result.violations)

    def test_outlier_not_similar_passes(self, create_context):
        """出現が少なくても支配的な値と類似しない場合は違反なし"""
        # "hello" は "はい" と文字レベルで類似しない
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "回答"],
                    *[[name, "はい"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "hello"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_free_text_column_skipped(self, create_context):
        """全列がカーディナリティ超過でスキップされた場合はルール自体をスキップする"""
        # 21 unique → cardinality > _MAX_CARDINALITY=20 → スキップ → confidence=0.0
        rows = [["名前", "コメント"]] + [[f"人{i}", f"コメント{i}"] for i in range(21)]
        ctx = create_context({"Sheet1": rows})
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.confidence == 0.0

    def test_numeric_column_skipped(self, create_context):
        """ColumnSchema で numeric と判定された列はスキップする"""
        # "１００" は NFKC で "100" に一致するが、numeric 列なので検出されない
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "金額"],
                    *[[name, "100"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "１００"],
                ],
            },
            column_schemas=[
                ColumnSchema(col_index=1, inferred_type="text"),
                ColumnSchema(col_index=2, inferred_type="numeric"),
            ],
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_too_few_rows_skipped(self, create_context):
        """全列がデータ不足でスキップされた場合はルール自体をスキップする"""
        # 4行 < _MIN_BODY_ROWS=20 → 全列スキップ → ルールスキップ（confidence=0.0）
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "回答"],
                    ["田中", "はい"],
                    ["鈴木", "はい"],
                    ["佐藤", "はい"],
                    ["渡辺", "はい ※別途確認"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.confidence == 0.0

    def test_dominant_values_empty_skipped(self, create_context):
        """全値が外れ値閾値以下（比較対象なし）の場合はスキップする"""
        # 20 unique values × 1回 → ratio=1/20=0.05 → 全て outlier → dominant 空 → スキップ
        rows = [["名前", "回答"]] + [[f"人{i:02d}", f"値{i:02d}"] for i in range(20)]
        ctx = create_context({"Sheet1": rows})
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_score_decreases_with_violations(self, create_context):
        """違反がある場合スコアが100未満になる"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "対象"],
                    *[[name, "該当する"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "該当する ※注釈a"],
                ],
            }
        )
        result = ChoiceStandardizationRule().check(ctx)
        assert result.passed is False
        # 違反が発生していることを確認（旧 score 範囲チェックは廃止）
        assert len(result.violations) > 0

    def test_ai_detects_semantic_variants(self, create_context):
        """AI が文字類似度では検出できない表記揺れを全分布スキャンで検出する"""
        # "受診した" は "受けた" と文字類似度が低いため決定論的には未検出
        # AI が全ユニーク値をスキャンし表記揺れグループを返す
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "受診状況"],
                    *[[name, "受けた"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "受診した"],
                ],
            }
        )
        with patch("harunobu.rules.level2.L2_04_choice_standardization.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_choice_variants.return_value = [["受けた", "受診した"]]
            MockClass.get_instance.return_value = mock_ai

            result = ChoiceStandardizationRule().check(ctx)

        assert result.passed is False
        assert any("受診した" in v.description for v in result.violations)
        assert result.confidence == 0.85

    def test_ai_detects_high_frequency_variants(self, create_context):
        """出現数が多い値同士の表記揺れも AI が検出できる"""
        # "取組済": 11件, "取り組み済": 9件 → どちらも outlier でないが AI が検出
        rows = (
            [["名前", "状況"]]
            + [[f"名前{i:02d}", "取組済"] for i in range(11)]
            + [[f"名前{i:02d}", "取り組み済"] for i in range(11, 20)]
        )
        ctx = create_context({"Sheet1": rows})
        with patch("harunobu.rules.level2.L2_04_choice_standardization.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_choice_variants.return_value = [["取組済", "取り組み済"]]
            MockClass.get_instance.return_value = mock_ai

            result = ChoiceStandardizationRule().check(ctx)

        # canonical は出現数最大の "取組済" → "取り組み済" が違反
        assert result.passed is False
        assert any("取り組み済" in v.description for v in result.violations)
        assert not any(v.description.startswith("表記揺れの可能性（AI検出）: '取組済'") for v in result.violations), (
            "canonical である '取組済' は違反として記録されてはならない"
        )

    def test_ai_no_duplicate_when_deterministic_already_detected(self, create_context):
        """決定論的に検出済みの値は AI 結果でも重複して記録されない"""
        # 注釈サフィックスは決定論的に検出 → AI が同じグループを返しても追加されない
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "対象"],
                    *[[name, "該当する"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "該当する ※注釈a"],
                ],
            }
        )
        with patch("harunobu.rules.level2.L2_04_choice_standardization.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_choice_variants.return_value = [["該当する", "該当する ※注釈a"]]
            MockClass.get_instance.return_value = mock_ai

            result = ChoiceStandardizationRule().check(ctx)

        assert result.passed is False
        assert len(result.violations) == 1

    def test_ai_skipped_when_single_unique_value(self, create_context):
        """列のユニーク値が 1 つの場合は AI を呼ばない"""
        rows = [["名前", "回答"]] + [[f"名前{i:02d}", "はい"] for i in range(20)]
        ctx = create_context({"Sheet1": rows})
        with patch("harunobu.rules.level2.L2_04_choice_standardization.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            MockClass.get_instance.return_value = mock_ai

            result = ChoiceStandardizationRule().check(ctx)

        mock_ai.check_choice_variants.assert_not_called()
        assert result.passed is True
        assert len(result.violations) == 0

    def test_ai_unavailable_only_deterministic_checked(self, create_context):
        """AI 利用不可の場合は決定論的チェックのみ実行する"""
        # "受診した" は決定論的に検出されないため違反なし
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "受診状況"],
                    *[[name, "受けた"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "受診した"],
                ],
            }
        )
        with patch("harunobu.rules.level2.L2_04_choice_standardization.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai

            result = ChoiceStandardizationRule().check(ctx)

        assert result.passed is True
        assert len(result.violations) == 0
        assert result.confidence == 0.7

    def test_ai_import_error_fallback(self, create_context):
        """AISemanticChecker が None（ImportError 相当）の場合もエラーなく動作する"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "受診状況"],
                    *[[name, "受けた"] for name in _NAMES[:-1]],
                    [_NAMES[-1], "受診した"],
                ],
            }
        )
        with patch("harunobu.rules.level2.L2_04_choice_standardization.AISemanticChecker", None):
            result = ChoiceStandardizationRule().check(ctx)

        assert result.passed is True
        assert result.confidence == 0.7
