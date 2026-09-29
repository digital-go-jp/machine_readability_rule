"""AISemanticChecker のテスト

AI が利用できない環境でも全テストが通過するように設計。
モックは is_available() と _generate_json() を直接上書きする方法で統一する。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from harunobu.core.ai_semantic_checker import AISemanticChecker


@pytest.fixture(autouse=True)
def reset_singleton():
    """各テスト前後にシングルトンをリセットする。"""
    AISemanticChecker.reset_instance()
    yield
    AISemanticChecker.reset_instance()


def make_mock_checker(mock_responses: dict | None = None) -> AISemanticChecker:
    """テスト用のモックチェッカーを生成する。

    Args:
        mock_responses:
            メソッド名 → 返り値のマッピング。指定されないメソッドは None を返す。
    """
    checker = AISemanticChecker()
    # is_available() を直接 True に固定
    checker.is_available = MagicMock(return_value=True)  # type: ignore[method-assign]
    # _generate_json はデフォルト None
    checker._generate_json = MagicMock(return_value=None)  # type: ignore[method-assign]

    if mock_responses:
        for method_name, return_value in mock_responses.items():
            setattr(checker, method_name, MagicMock(return_value=return_value))

    return checker


def make_unavailable_checker() -> AISemanticChecker:
    """AI unavailable なチェッカーを生成する。"""
    checker = AISemanticChecker()
    checker.is_available = MagicMock(return_value=False)  # type: ignore[method-assign]
    return checker


class TestAISemanticCheckerAvailability:
    """is_available() のテスト"""

    def test_unavailable_without_credentials(self, monkeypatch):
        """認証情報なしで unavailable"""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
        monkeypatch.delenv("HARUNOBU_AI_DISABLED", raising=False)
        checker = AISemanticChecker()
        # google-genai が未インストールまたは認証なしで False
        assert checker.is_available() is False

    def test_unavailable_when_disabled_env(self, monkeypatch):
        """HARUNOBU_AI_DISABLED=1 で常に unavailable"""
        monkeypatch.setenv("HARUNOBU_AI_DISABLED", "1")
        checker = AISemanticChecker()
        assert checker.is_available() is False

    def test_singleton_returns_same_instance(self):
        """get_instance() が同一インスタンスを返す"""
        a = AISemanticChecker.get_instance()
        b = AISemanticChecker.get_instance()
        assert a is b

    def test_reset_instance_creates_new(self):
        """reset_instance() 後は新しいインスタンスが返される"""
        a = AISemanticChecker.get_instance()
        AISemanticChecker.reset_instance()
        b = AISemanticChecker.get_instance()
        assert a is not b


class TestCheckAbbreviations:
    """check_abbreviations() のテスト"""

    def test_returns_empty_when_ai_unavailable(self):
        """AI unavailable なら空リストを返す"""
        checker = make_unavailable_checker()
        result = checker.check_abbreviations([(1, 1, "東京"), (2, 1, "")], "都道府県")
        assert result == []

    def test_returns_empty_for_empty_input(self):
        """空データには空リストを返す"""
        checker = make_mock_checker()
        checker._generate_json = MagicMock(return_value=[])
        result = checker.check_abbreviations([], "都道府県")
        assert result == []

    def test_detects_abbreviations_from_ai_response(self):
        """AI レスポンスから省略を検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[{"row": 3, "value": "H30", "reason": "和暦略称"}])
        column_data = [(1, 1, "H28"), (2, 1, "H29"), (3, 1, "H30")]
        result = checker.check_abbreviations(column_data, "年度")
        assert len(result) == 1
        assert result[0]["row"] == 3
        assert result[0]["reason"] == "和暦略称"

    def test_ignores_invalid_rows_from_ai(self):
        """AI レスポンスに存在しない行番号が含まれていても無視する"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[{"row": 99, "value": "x", "reason": "存在しない行"}])
        column_data = [(1, 1, "東京")]
        result = checker.check_abbreviations(column_data, "都道府県")
        assert result == []

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合は空リストを返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.check_abbreviations([(1, 1, "東京")], "都道府県")
        assert result == []

    def test_col_mapping_is_correct(self):
        """row→col マッピングが正しく動作する"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[{"row": 2, "value": "H29", "reason": "略称"}])
        # col=3 のデータ
        column_data = [(1, 3, "H28"), (2, 3, "H29"), (3, 3, "H30")]
        result = checker.check_abbreviations(column_data, "年度")
        assert len(result) == 1
        assert result[0]["col"] == 3


class TestCheckWideFormatSemantic:
    """check_wide_format_semantic() のテスト"""

    def test_returns_not_wide_when_ai_unavailable(self):
        """AI unavailable なら is_wide=False を返す"""
        checker = make_unavailable_checker()
        result = checker.check_wide_format_semantic(["北海道", "青森県", "岩手県"])
        assert result["is_wide"] is False
        assert result["confidence"] == 0.0

    def test_detects_prefecture_wide_format(self):
        """都道府県が列名の横持ち形式を検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "is_wide": True,
                "category_type": "都道府県",
                "details": "47都道府県が列名になっています",
                "confidence": 0.95,
            }
        )
        result = checker.check_wide_format_semantic(["北海道", "青森県", "岩手県", "宮城県"])
        assert result["is_wide"] is True
        assert result["category_type"] == "都道府県"
        assert result["confidence"] == 0.95

    def test_returns_not_wide_for_normal_headers(self):
        """通常の項目名では横持ちでないと返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={"is_wide": False, "category_type": "", "details": "", "confidence": 0.1}
        )
        result = checker.check_wide_format_semantic(["名称", "人口", "面積"])
        assert result["is_wide"] is False

    def test_empty_headers_returns_not_wide(self):
        """空のヘッダーリストは is_wide=False を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        result = checker.check_wide_format_semantic([])
        assert result["is_wide"] is False

    def test_sample_rows_passed_to_ai(self):
        """sample_rows が AI に渡されることを確認"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={"is_wide": False, "category_type": "", "details": "", "confidence": 0.1}
        )
        sample = [["100", "200"], ["150", "250"]]
        checker.check_wide_format_semantic(["A", "B"], sample_rows=sample)
        # プロンプトにサンプルデータが含まれることを確認
        call_args = checker._generate_json.call_args[0][0]
        assert "100" in call_args or "150" in call_args


class TestCheckSpecialSymbolIntent:
    """check_special_symbol_intent() のテスト"""

    def test_returns_marker_true_when_ai_unavailable(self):
        """AI unavailable なら保守的に is_statistical_marker=True を返す"""
        checker = make_unavailable_checker()
        result = checker.check_special_symbol_intent("-", "人口", ["100", "200", "-"])
        assert result["is_statistical_marker"] is True

    def test_detects_statistical_marker(self):
        """AI が統計マーカーと判定する"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={"is_statistical_marker": True, "likely_meaning": "該当なし", "confidence": 0.9}
        )
        result = checker.check_special_symbol_intent("-", "件数", ["100", "200", "-", "150"])
        assert result["is_statistical_marker"] is True
        assert result["likely_meaning"] == "該当なし"

    def test_filters_negative_number_hyphen(self):
        """負の数値の列では `-` を統計マーカーでないと判定できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={"is_statistical_marker": False, "likely_meaning": "負の値の一部", "confidence": 0.8}
        )
        result = checker.check_special_symbol_intent("-", "増減数", ["-100", "200", "-50"])
        assert result["is_statistical_marker"] is False

    def test_none_response_returns_default_marker(self):
        """_generate_json が None なら保守的に True を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.check_special_symbol_intent("x", "秘匿列", ["100", "x", "200"])
        assert result["is_statistical_marker"] is True


class TestCheckChoiceVariants:
    """check_choice_variants() のテスト"""

    def test_returns_empty_when_ai_unavailable(self):
        """AI unavailable なら空リストを返す"""
        checker = make_unavailable_checker()
        result = checker.check_choice_variants(["有", "あり", "無"], "区分")
        assert result == []

    def test_detects_variant_groups(self):
        """意味的に同じグループを検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[["受けた", "受診した"]])
        result = checker.check_choice_variants(["受けた", "受診した", "未受診"], "受診状況")
        assert len(result) == 1
        assert set(result[0]) == {"受けた", "受診した"}

    def test_filters_groups_with_unknown_values(self):
        """AI が返したグループに実際に存在しない値があれば除外"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[["受けた", "未知の値", "受診した"]])
        result = checker.check_choice_variants(["受けた", "受診した"], "受診状況")
        # "未知の値" は除外され、残り2つでグループ成立
        assert len(result) == 1
        assert "未知の値" not in result[0]

    def test_returns_empty_for_single_unique_value(self):
        """ユニーク値が1つ以下なら空を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        result = checker.check_choice_variants(["有", "有", "有"], "区分")
        assert result == []

    def test_returns_empty_for_too_many_unique_values(self):
        """ユニーク値が50超なら AI を呼ばず空を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[])
        values = [str(i) for i in range(60)]
        result = checker.check_choice_variants(values, "自由記述")
        # ユニーク値 > 50 なので AI は呼ばれない
        checker._generate_json.assert_not_called()
        assert result == []


class TestInferUnitFromHeader:
    """infer_unit_from_header() のテスト"""

    def test_returns_no_unit_when_ai_unavailable(self):
        """AI unavailable なら has_unit=False を返す"""
        checker = make_unavailable_checker()
        result = checker.infer_unit_from_header("DI値", [50, -10, 30])
        assert result["has_unit"] is False

    def test_infers_di_unit(self):
        """DI値の単位を推測できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={"has_unit": True, "inferred_unit": "指数", "explanation": "DI値は指数"}
        )
        result = checker.infer_unit_from_header("DI値", [50, -10, 30])
        assert result["has_unit"] is True
        assert result["inferred_unit"] == "指数"

    def test_infers_percentage_for_rate_column(self):
        """「受診率」を % 単位ありと推測できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={"has_unit": True, "inferred_unit": "%", "explanation": "受診率は百分率"}
        )
        result = checker.infer_unit_from_header("受診率", [82.5, 79.3, 91.0])
        assert result["has_unit"] is True


class TestCheckCodeNeedsTable:
    """check_code_needs_table() のテスト"""

    def test_returns_false_when_ai_unavailable(self):
        """AI unavailable なら needs_code_table=False を返す"""
        checker = make_unavailable_checker()
        result = checker.check_code_needs_table("性別", [1, 2, 1, 2])
        assert result["needs_code_table"] is False

    def test_detects_gender_code(self):
        """性別コードを検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "needs_code_table": True,
                "code_type": "性別コード",
                "explanation": "1=男, 2=女のコード値",
            }
        )
        result = checker.check_code_needs_table("性別", [1, 2, 1, 1, 2])
        assert result["needs_code_table"] is True
        assert result["code_type"] == "性別コード"

    def test_does_not_flag_counts(self):
        """件数・人数はコードではないと判定できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "needs_code_table": False,
                "code_type": "",
                "explanation": "人数は数値データでコードではない",
            }
        )
        result = checker.check_code_needs_table("人数", [100, 200, 150])
        assert result["needs_code_table"] is False

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合はデフォルト値を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.check_code_needs_table("区分", [1, 2, 3])
        assert result["needs_code_table"] is False


class TestCheckUnitInCell:
    """check_unit_in_cell() のテスト"""

    def test_returns_fallback_when_ai_unavailable(self):
        """AI unavailable ならフォールバック値を返す"""
        checker = make_unavailable_checker()
        result = checker.check_unit_in_cell("約1,200名", "人口")
        assert result["has_unit"] is False
        assert result["numeric_part"] == "約1,200名"
        assert result["unit_part"] == ""
        assert result["confidence"] == 0.0

    def test_detects_unit_in_cell(self):
        """セル値に混在する単位を検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "has_unit": True,
                "numeric_part": "1200",
                "unit_part": "名",
                "confidence": 0.95,
            }
        )
        result = checker.check_unit_in_cell("約1,200名（前年比+2%）", "利用者数")
        assert result["has_unit"] is True
        assert result["numeric_part"] == "1200"
        assert result["unit_part"] == "名"
        assert result["confidence"] == 0.95

    def test_pure_number_has_no_unit(self):
        """純粋な数値は単位なしと判定できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "has_unit": False,
                "numeric_part": "1234",
                "unit_part": "",
                "confidence": 0.9,
            }
        )
        result = checker.check_unit_in_cell("1,234", "件数")
        assert result["has_unit"] is False

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合はフォールバック値を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.check_unit_in_cell("500千円", "予算")
        assert result["has_unit"] is False
        assert result["numeric_part"] == "500千円"


class TestCheckOtherDetailMixed:
    """check_other_detail_mixed() のテスト"""

    def test_returns_fallback_when_ai_unavailable(self):
        """AI unavailable ならフォールバック値を返す"""
        checker = make_unavailable_checker()
        result = checker.check_other_detail_mixed("その他_駐車場利用", "区分")
        assert result["is_mixed"] is False
        assert result["other_part"] == ""
        assert result["detail_part"] == ""
        assert result["confidence"] == 0.0

    def test_detects_mixed_pattern(self):
        """「その他_詳細」パターンを検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "is_mixed": True,
                "other_part": "その他",
                "detail_part": "駐車場利用",
                "confidence": 0.9,
            }
        )
        result = checker.check_other_detail_mixed("その他_駐車場利用", "施設区分")
        assert result["is_mixed"] is True
        assert result["other_part"] == "その他"
        assert result["detail_part"] == "駐車場利用"

    def test_not_mixed_for_standalone_other(self):
        """単独の「その他」は混在でないと判定できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "is_mixed": False,
                "other_part": "",
                "detail_part": "",
                "confidence": 0.85,
            }
        )
        result = checker.check_other_detail_mixed("その他", "区分")
        assert result["is_mixed"] is False

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合はフォールバック値を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.check_other_detail_mixed("その他（施設管理）", "区分")
        assert result["is_mixed"] is False


class TestNormalizeTimeValue:
    """normalize_time_value() のテスト"""

    def test_returns_fallback_when_ai_unavailable(self):
        """AI unavailable ならフォールバック値を返す"""
        checker = make_unavailable_checker()
        result = checker.normalize_time_value("H29", "年度")
        assert result["normalized"] == ""
        assert result["original_era"] == ""
        assert result["confidence"] == 0.0

    def test_normalizes_heisei(self):
        """平成の和暦略称を西暦に正規化できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "normalized": "2017",
                "original_era": "平成",
                "confidence": 0.99,
            }
        )
        result = checker.normalize_time_value("H29", "年度")
        assert result["normalized"] == "2017"
        assert result["original_era"] == "平成"

    def test_normalizes_reiwa(self):
        """令和の和暦略称を西暦に正規化できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "normalized": "2021",
                "original_era": "令和",
                "confidence": 0.99,
            }
        )
        result = checker.normalize_time_value("R3", "年度")
        assert result["normalized"] == "2021"
        assert result["original_era"] == "令和"

    def test_handles_western_year(self):
        """西暦はそのまま返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "normalized": "2020",
                "original_era": "",
                "confidence": 0.95,
            }
        )
        result = checker.normalize_time_value("2020年度", "年度")
        assert result["normalized"] == "2020"
        assert result["original_era"] == ""

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合はフォールバック値を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.normalize_time_value("H29", "年度")
        assert result["normalized"] == ""


class TestCheckMetadataQuality:
    """check_metadata_quality() のテスト"""

    def test_returns_fallback_when_ai_unavailable(self):
        """AI unavailable ならフォールバック値を返す"""
        checker = make_unavailable_checker()
        result = checker.check_metadata_quality(["人口", "面積"], ["タイトル"])
        assert result["quality_score"] == 0.0
        assert result["missing_items"] == []
        assert result["suggestions"] == []

    def test_evaluates_metadata_quality(self):
        """メタデータ品質を評価できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "quality_score": 0.4,
                "missing_items": ["出典", "対象期間", "単位"],
                "suggestions": ["数値列に単位を明記してください", "出典を記載してください"],
            }
        )
        result = checker.check_metadata_quality(
            ["都道府県", "人口", "面積"],
            ["タイトル"],
        )
        assert result["quality_score"] == 0.4
        assert "出典" in result["missing_items"]
        assert len(result["suggestions"]) == 2

    def test_high_quality_metadata(self):
        """十分なメタデータがある場合は高スコアを返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "quality_score": 0.9,
                "missing_items": [],
                "suggestions": [],
            }
        )
        result = checker.check_metadata_quality(
            ["都道府県", "人口（人）"],
            ["タイトル", "出典", "作成日", "対象期間"],
        )
        assert result["quality_score"] == 0.9
        assert result["missing_items"] == []

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合はフォールバック値を返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.check_metadata_quality(["人口"], [])
        assert result["quality_score"] == 0.0
        assert result["missing_items"] == []

    def test_handles_invalid_list_fields(self):
        """AI が missing_items/suggestions を非リストで返した場合も安全にハンドルする"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value={
                "quality_score": 0.5,
                "missing_items": "出典",  # リストでなく文字列
                "suggestions": None,  # None
            }
        )
        result = checker.check_metadata_quality(["人口"], [])
        assert result["missing_items"] == []
        assert result["suggestions"] == []


class TestAssessColumnHeaderClarity:
    """assess_column_header_clarity() のテスト"""

    def test_returns_empty_when_ai_unavailable(self):
        """AI unavailable なら空リストを返す"""
        checker = make_unavailable_checker()
        result = checker.assess_column_header_clarity(["値", "区分", "人口"])
        assert result == []

    def test_returns_empty_for_empty_headers(self):
        """空のヘッダーリストなら空リストを返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        result = checker.assess_column_header_clarity([])
        assert result == []

    def test_detects_ambiguous_headers(self):
        """曖昧なヘッダーを検出できる"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value=[
                {
                    "header": "値",
                    "is_ambiguous": True,
                    "suggested_improvement": "人口（人）",
                    "reason": "何の値か不明",
                },
                {
                    "header": "区分",
                    "is_ambiguous": True,
                    "suggested_improvement": "性別区分",
                    "reason": "何の区分か不明",
                },
            ]
        )
        result = checker.assess_column_header_clarity(["値", "区分", "人口"])
        assert len(result) == 2
        assert result[0]["header"] == "値"
        assert result[0]["is_ambiguous"] is True
        assert result[1]["header"] == "区分"

    def test_returns_empty_for_clear_headers(self):
        """明確なヘッダーのみの場合は空リストを返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=[])
        result = checker.assess_column_header_clarity(["都道府県名", "人口（人）", "面積（km²）"])
        assert result == []

    def test_filters_unknown_headers_from_ai(self):
        """AI が返したヘッダーが実際のヘッダーに存在しない場合は除外する"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(
            return_value=[
                {
                    "header": "値",
                    "is_ambiguous": True,
                    "suggested_improvement": "数量",
                    "reason": "曖昧",
                },
                {
                    "header": "存在しないヘッダー",
                    "is_ambiguous": True,
                    "suggested_improvement": "xxx",
                    "reason": "不明",
                },
            ]
        )
        result = checker.assess_column_header_clarity(["値", "人口"])
        assert len(result) == 1
        assert result[0]["header"] == "値"

    def test_handles_none_response_gracefully(self):
        """_generate_json が None を返す場合は空リストを返す"""
        checker = AISemanticChecker()
        checker.is_available = MagicMock(return_value=True)
        checker._generate_json = MagicMock(return_value=None)
        result = checker.assess_column_header_clarity(["値", "区分"])
        assert result == []
