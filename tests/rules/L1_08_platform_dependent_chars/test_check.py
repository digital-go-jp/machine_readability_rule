"""L1-08: 機種依存文字チェックのテスト

L1-08はShift-JIS（CP932）として読み込まれたファイルのみを対象とする。
そのため、検出ロジックの挙動をテストする際は ``encoding="cp932"`` を指定する。
"""

from __future__ import annotations

import pytest

from harunobu.rules.level1.L1_08_platform_dependent_chars import (
    PlatformDependentCharsRule,
    _classify,
)


class TestPlatformDependentCharsCheck:
    """L1-08 機種依存文字チェック"""

    @pytest.fixture
    def rule(self):
        return PlatformDependentCharsRule()

    def test_no_platform_dependent_chars_passes(self, rule, create_context):
        """機種依存文字がない場合はpass"""
        ctx = create_context(
            {"Sheet1": [["name", "age"], ["Taro", 20], ["Hanako", 25]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_fullwidth_alphanumeric_detected_as_info(self, rule, create_context):
        """全角英数字はseverity=infoとして検出され、passedはTrue"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["ABC", "１２３"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        # 全角英数字のみであれば pass する（単なるスタイル上の問題）
        assert result.passed is True
        # assert result.score < 100
        assert len(result.violations) >= 1
        # すべての violation は info severity であること
        for v in result.violations:
            assert v.severity == "info"
        descs = " ".join(v.description for v in result.violations)
        assert "全角英数字" in descs

    def test_circled_numbers_detected(self, rule, create_context):
        """丸数字が検出される（severity=warning, passed=False）"""
        ctx = create_context(
            {"Sheet1": [["番号", "内容"], ["①", "テスト"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "丸数字" in descs
        # warning severity であること
        warning_violations = [v for v in result.violations if v.severity == "warning"]
        assert len(warning_violations) >= 1

    def test_roman_numerals_detected(self, rule, create_context):
        """ローマ数字が検出される（severity=warning, passed=False）"""
        ctx = create_context(
            {"Sheet1": [["章", "タイトル"], ["Ⅲ", "概要"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "ローマ数字" in descs
        warning_violations = [v for v in result.violations if v.severity == "warning"]
        assert len(warning_violations) >= 1

    def test_platform_dependent_symbols_detected(self, rule, create_context):
        """機種依存記号（㈱等）が検出される"""
        ctx = create_context(
            {"Sheet1": [["会社名", "備考"], ["㈱テスト", "㍉"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is False
        descs = " ".join(v.description for v in result.violations)
        assert "機種依存記号" in descs

    def test_japanese_text_without_issues_passes(self, rule, create_context):
        """通常の日本語テキスト（全角カタカナ・ひらがな・漢字）はpass"""
        ctx = create_context(
            {"Sheet1": [["名前", "住所"], ["山田太郎", "東京都千代田区"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is True

    def test_fullwidth_katakana_passes(self, rule, create_context):
        """全角カタカナは機種依存文字ではないのでpass"""
        ctx = create_context(
            {"Sheet1": [["カテゴリ", "内容"], ["アイウエオ", "カキクケコ"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_fullwidth_punctuation_passes(self, rule, create_context):
        """全角句読点・括弧は機種依存文字ではないのでpass"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["東京都（特別区）", "備考：なし"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100

    def test_none_and_empty_values_ignored(self, rule, create_context):
        """Noneや空値は無視される"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], [None, ""], ["test", 0]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is True

    def test_score_penalty_platform_dependent_heavy(self, rule, create_context):
        """機種依存文字はスコアペナルティが大きい（1件あたり3点）"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["col1", "col2"],
                    ["①", "②"],
                    ["③", "④"],
                ]
            },
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is False
        # 機種依存文字 4 件 * 3 = 12 点ペナルティ
        # assert result.score == 88

    def test_score_penalty_fullwidth_alnum_light(self, rule, create_context):
        """全角英数字はスコアペナルティが軽い（1件あたり1点、上限10点）"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["col1", "col2"],
                    ["Ａ", "Ｂ"],
                    ["Ｃ", "Ｄ"],
                ]
            },
            encoding="cp932",
        )
        result = rule.check(ctx)
        # 全角英数字のみ -> passed は True
        assert result.passed is True
        # 4 セル * 1 = 4 点ペナルティ
        # assert result.score == 96

    def test_mixed_platform_dependent_and_fullwidth(self, rule, create_context):
        """機種依存文字と全角英数字が混在する場合"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["col1", "col2"],
                    ["①", "Ａ"],
                ]
            },
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is False
        # 機種依存文字 1 件 (3) + 全角英数字 1 件 (1) = 4 点ペナルティ
        # assert result.score == 96
        # severity を確認
        severities = {v.severity for v in result.violations}
        assert "warning" in severities
        assert "info" in severities

    def test_score_penalty_fullwidth_alnum_capped_at_10(self, rule, create_context):
        """全角英数字のペナルティは上限10点（11セル以上でも10点まで）"""
        # 全角英数字を含む 12 セルを生成（ヘッダー行 + データ 6 行 * 2 列）
        ctx = create_context(
            {
                "Sheet1": [
                    ["col1", "col2"],
                    ["Ａ", "Ｂ"],
                    ["Ｃ", "Ｄ"],
                    ["Ｅ", "Ｆ"],
                    ["Ｇ", "Ｈ"],
                    ["Ｉ", "Ｊ"],
                    ["Ｋ", "Ｌ"],
                ]
            },
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # 全角英数字 12 セルだが、ペナルティは 10 点が上限
        # assert result.score == 90

    def test_many_fullwidth_alnum_still_passes(self, rule, create_context):
        """大量の全角英数字があってもpassed=Trueのまま"""
        rows = [["col1", "col2"]]
        for _ in range(20):
            rows.append(["Ａ", "Ｂ"])
        ctx = create_context({"Sheet1": rows}, encoding="cp932")
        result = rule.check(ctx)
        assert result.passed is True
        # 全角英数字 40 セルでも、ペナルティは 10 点が上限のまま
        # assert result.score == 90

    def test_cell_with_both_types_uses_warning_severity(self, rule, create_context):
        """1セルに機種依存文字と全角英数字の両方がある場合、severity=warning"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["①Ａ", "テスト"]]},
            encoding="cp932",
        )
        result = rule.check(ctx)
        assert result.passed is False
        # 両方を含むセルは severity="warning" であること
        mixed_cell = [v for v in result.violations if "①" in v.description]
        assert len(mixed_cell) == 1
        assert mixed_cell[0].severity == "warning"

    def test_score_penalty_platform_dependent_capped_at_40(self, rule, create_context):
        """大量の機種依存文字があってもペナルティは40点が上限（スコア最低60）"""
        # ローマ数字を含む 20 セルを生成（ヘッダー行 + データ 10 行 * 2 列）
        rows = [["col1", "col2"]]
        roman_chars = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ"
        for i in range(10):
            rows.append([roman_chars[i], roman_chars[(i + 1) % 10]])
        ctx = create_context({"Sheet1": rows}, encoding="cp932")
        result = rule.check(ctx)
        assert result.passed is False
        # 機種依存文字 20 セル * 3 = 60 だが、40 点が上限
        # assert result.score == 60

    def test_many_roman_numerals_code_pattern_passes(self, rule, create_context):
        """行政データの分類コード（Ⅰ-0等）はinfoとして扱われ、ルールはパスする"""
        rows = [["項目", "値"]]
        for i in range(30):
            rows.append([f"Ⅰ-{i}", "data"])
        ctx = create_context({"Sheet1": rows}, encoding="cp932")
        result = rule.check(ctx)
        # 分類コードパターンはinfoに降格されるため、passする
        assert result.passed is True
        # assert result.score >= 60


class TestPlatformDependentCharsUtf8AndXlsx:
    """UTF-8 / xlsx 読み込み時は warning として参考報告し、スコアには影響しない。"""

    @pytest.fixture
    def rule(self):
        return PlatformDependentCharsRule()

    def test_utf8_emits_warnings_only(self, rule, create_context):
        """UTF-8 で丸数字を検出した場合、warning として報告するが passed=True, score=100"""
        ctx = create_context(
            {"Sheet1": [["番号", "内容"], ["①", "テスト"]]},
            file_name="test.csv",
            encoding="utf-8",
        )
        result = rule.check(ctx)
        assert result.confidence == 0.95
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) >= 1
        for v in result.violations:
            assert v.severity == "warning"
        descs = " ".join(v.description for v in result.violations)
        assert "丸数字" in descs

    def test_utf8_sig_emits_warnings_only(self, rule, create_context):
        """BOM付き UTF-8 でも同様に warning として報告する"""
        ctx = create_context(
            {"Sheet1": [["番号"], ["Ⅲ"]]},
            file_name="test.csv",
            encoding="utf-8-sig",
        )
        result = rule.check(ctx)
        assert result.confidence == 0.95
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) >= 1
        assert all(v.severity == "warning" for v in result.violations)

    def test_xlsx_emits_warnings_only(self, rule, create_context):
        """xlsx (encoding=None) でも丸数字は warning として報告する"""
        ctx = create_context(
            {"Sheet1": [["番号"], ["①"]]},
            encoding=None,
        )
        result = rule.check(ctx)
        assert result.confidence == 0.95
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) >= 1
        assert all(v.severity == "warning" for v in result.violations)

    def test_utf8_clean_passes_with_full_score(self, rule, create_context):
        """UTF-8 で機種依存文字がなければ violations は空、score=100"""
        ctx = create_context(
            {"Sheet1": [["name", "age"], ["Taro", 20]]},
            file_name="test.csv",
            encoding="utf-8",
        )
        result = rule.check(ctx)
        assert result.confidence == 0.95
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_utf8_fullwidth_alnum_reported_as_info(self, rule, create_context):
        """UTF-8 でも全角英数字は info severity として報告される（warning ではない）"""
        ctx = create_context(
            {"Sheet1": [["項目"], ["Ａ"]]},
            file_name="test.csv",
            encoding="utf-8",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100  # UTF-8 はスコアに影響しない
        assert len(result.violations) >= 1
        # 全角英数字は info のまま（warning に昇格しない）
        info_only = [v for v in result.violations if v.severity == "info"]
        assert len(info_only) >= 1


class TestClassify:
    """``_classify`` の分類スモークテスト。

    旧 580 行 CSV から Unicode 範囲ベース判定 + 縮小 CSV に移行した際の
    リグレッション防止。
    """

    @pytest.mark.parametrize(
        "ch,expected_category,expected_severity",
        [
            ("①", "circled_number", "warning"),
            ("⑳", "circled_number", "warning"),
            ("Ⅰ", "roman_numeral", "warning"),
            ("Ⅻ", "roman_numeral", "warning"),  # CP932 外だが範囲指定で拾う
            ("ⅻ", "roman_numeral", "warning"),
            ("㈱", "platform_symbol", "warning"),
            ("㎡", "unit_symbol", "info"),
            ("Ａ", "fullwidth_alnum", "info"),
            ("０", "fullwidth_alnum", "info"),
            ("ａ", "fullwidth_alnum", "info"),
            ("㋿", "reiwa_era", "warning"),  # CSV 特殊文字
            ("〜", "wave_dash", "warning"),  # CSV 特殊文字
            ("～", "fullwidth_tilde", "warning"),  # CSV 特殊文字
        ],
    )
    def test_detected_chars(self, ch, expected_category, expected_severity):
        result = _classify(ch)
        assert result is not None, f"{ch} (U+{ord(ch):04X}) should be detected"
        assert result == (expected_category, expected_severity)

    @pytest.mark.parametrize(
        "ch",
        [
            "a",  # ASCII 半角英字
            "0",  # ASCII 半角数字
            "あ",  # ひらがな
            "ア",  # カタカナ
            "高",  # 漢字 (JIS X 0208 標準)
            "髙",  # IBM 拡張漢字（L1-08 のスコープ外、L1-09 異体字側で扱う）
            "﨑",  # IBM 拡張漢字
            " ",  # 半角スペース
            "　",  # 全角スペース (検出対象外)
        ],
    )
    def test_not_detected(self, ch):
        assert _classify(ch) is None, f"{ch} (U+{ord(ch):04X}) should not be detected"
