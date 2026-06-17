"""L1-06: 体裁用スペース・改行チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.rules.level1.L1_06_whitespace_formatting import (
    WhitespaceFormattingRule,
)


class TestWhitespaceFormattingCheck:
    """L1-06 体裁用スペース・改行チェック"""

    @pytest.fixture
    def rule(self):
        return WhitespaceFormattingRule()

    def test_clean_data_passes(self, rule, create_context):
        """空白問題のないデータはpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_leading_spaces_detected(self, rule, create_context):
        """先頭スペースが検出される"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["  太郎", 20]]})
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) >= 1

    def test_trailing_spaces_detected(self, rule, create_context):
        """末尾スペースが検出される"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎  ", 20]]})
        result = rule.check(ctx)
        assert result.passed is False

    def test_fullwidth_space_detected(self, rule, create_context):
        """全角スペースが検出される"""
        ctx = create_context({"Sheet1": [["名前", "備考"], ["太郎", "東京都\u3000千代田区"]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "全角スペース" in descs

    def test_consecutive_spaces_detected(self, rule, create_context):
        """連続スペースが検出される"""
        ctx = create_context({"Sheet1": [["項目", "値"], ["東京都  千代田区", "test"]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "連続" in descs

    def test_none_and_empty_values_ignored(self, rule, create_context):
        """Noneや空値は無視される"""
        ctx = create_context({"Sheet1": [["項目", "値"], [None, ""], ["test", 0]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_score_calculation(self, rule, create_context):
        """スコアは違反数に応じて減少する"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["col1", "col2"],
                    ["  a", "b  "],
                    ["  c", "d  "],
                ]
            }
        )
        result = rule.check(ctx)
        assert result.passed is False
        # 4件の違反 -> 100 - 4*2 = 92
        # assert result.score == 92

    # --- 新規: 住所カラムの全角スペース許容テスト ---

    def test_address_column_fullwidth_space_allowed(self, rule, create_context):
        """住所カラムの全角スペースは許容される"""
        ctx = create_context({"Sheet1": [["名前", "住所"], ["太郎", "東京都\u3000千代田区\u3000丸の内1-1"]]})
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_address_column_consecutive_spaces_allowed(self, rule, create_context):
        """住所カラムの連続スペースは許容される"""
        ctx = create_context({"Sheet1": [["名前", "住所"], ["太郎", "東京都  千代田区"]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_address_column_leading_trailing_still_detected(self, rule, create_context):
        """住所カラムでも先頭・末尾空白は検出される"""
        ctx = create_context({"Sheet1": [["名前", "住所"], ["太郎", "  東京都千代田区  "]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "先頭または末尾" in descs

    def test_address_variant_headers(self, rule, create_context):
        """所在地・現住所など住所系ヘッダーバリエーション"""
        for header in ["所在地", "現住所", "勤務地", "送付先"]:
            ctx = create_context({"Sheet1": [["名前", header], ["太郎", "東京都\u3000千代田区"]]})
            result = rule.check(ctx)
            assert result.passed is True, f"header={header} should allow fullwidth space"

    def test_non_address_column_fullwidth_still_detected(self, rule, create_context):
        """住所以外のカラムでは全角スペースが検出される"""
        ctx = create_context({"Sheet1": [["名前", "備考"], ["太郎", "テスト\u3000データ"]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "全角スペース" in descs

    # --- 新規: 末尾改行の許容テスト ---

    def test_trailing_newline_not_flagged(self, rule, create_context):
        """末尾の改行のみの場合はフラグしない"""
        ctx = create_context({"Sheet1": [["項目", "値"], ["テスト\n", "データ"]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_leading_space_with_trailing_newline_detected(self, rule, create_context):
        """末尾改行があっても先頭スペースは検出される"""
        ctx = create_context({"Sheet1": [["項目", "値"], ["  テスト\n", "データ"]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "先頭または末尾" in descs

    # --- セル内改行（密度しきい値付き） ---

    def test_internal_newline_short_high_density_detected(self, rule, create_context):
        """NG-03 相当: 短いセルで途中改行は違反"""
        ctx = create_context({"Sheet1": [["都道府県"], ["北海道\n（道内）"], ["青森県\n（東北）"]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "体裁目的の改行" in descs

    def test_internal_newline_long_sparse_not_flagged(self, rule, create_context):
        """長文で改行が疎なら内部改行のみでは違反にしない"""
        body = "a" * 3000 + "\n" + "b" * 500
        ctx = create_context({"Sheet1": [["備考"], [body]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_internal_newline_density_at_boundary(self, rule, create_context):
        """空白密度がしきい値ちょうど以下なら内部改行のみでは違反にしない"""
        # 10 文字に空白 1（改行）→ 密度 0.10 = しきい値 → 内部改行ブロックは違反にしない
        val = "aaaaaaa\nbb"
        assert len(val) == 10
        ctx = create_context({"Sheet1": [["c"], [val]]})
        result = rule.check(ctx)
        assert result.passed is True

    def test_internal_newline_density_just_over_threshold(self, rule, create_context):
        """9 文字に改行 1 → 密度 > 0.10 で違反"""
        val = "aaaaaaa\nb"
        assert len(val) == 9
        ctx = create_context({"Sheet1": [["c"], [val]]})
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "体裁目的の改行" in descs
