"""L3-09: データが縦持ち形式になっているかのテスト"""

from unittest.mock import MagicMock, patch

from harunobu.rules.level3.L3_09_vertical_format import VerticalFormatRule


class TestVerticalFormatCheck:
    """L3-09 縦持ちフォーマットチェック"""

    def test_vertical_format_passes(self, create_context):
        """縦持ち形式の場合に違反なし"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年", "値"],
                    ["太郎", 2021, 100],
                    ["太郎", 2022, 200],
                    ["花子", 2021, 150],
                    ["花子", 2022, 250],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_wide_format_year_columns_detected(self, create_context):
        """年が列名になっている横持ち形式を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "2019年", "2020年", "2021年", "2022年"],
                    ["太郎", 100, 200, 300, 400],
                    ["花子", 150, 250, 350, 450],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("横持ち" in v.description for v in result.violations)

    def test_few_columns_skipped(self, create_context):
        """列数が少ない場合は判定対象外"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "値"],
                    ["太郎", 100],
                    ["花子", 200],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_month_columns_horizontal_detected(self, create_context):
        """月が列名になっている横持ちを検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "1月", "2月", "3月", "4月"],
                    ["A市", 10, 20, 30, 40],
                    ["B市", 15, 25, 35, 45],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("横持ち" in v.description for v in result.violations)

    def test_wareki_year_columns_detected(self, create_context):
        """和暦年が列名になっている横持ちを検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "令和元年", "令和2年", "令和3年", "令和4年"],
                    ["A市", 100, 200, 300, 400],
                    ["B市", 150, 250, 350, 450],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("横持ち" in v.description for v in result.violations)

    def test_fiscal_year_code_columns_detected(self, create_context):
        """和暦短縮形 (R01〜R05 等) が列名の横持ちを time-axis として検出する。

        local_public_finance 配下の実データで頻出するパターンで、従来は
        「番号付き類似列 (info)」として info レベルでしか検出されなかった。
        正しく時間軸横持ち (warning) として検出されることを担保する。
        """
        ctx = create_context(
            {
                "Sheet1": [
                    ["年度", "R01", "R02", "R03", "R04", "R05"],
                    ["指標A", 100, 200, 300, 400, 500],
                    ["指標B", 150, 250, 350, 450, 550],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is False
        wareki_violation = next(
            (v for v in result.violations if "横持ち" in v.description and "年（和暦）" in v.description),
            None,
        )
        assert wareki_violation is not None, "和暦短縮形が time-axis として検出されるべき"
        assert wareki_violation.severity == "warning"

    def test_heisei_short_code_columns_detected(self, create_context):
        """平成短縮形 (H30 等) と令和短縮形が混在する横持ちを検出する。"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["指標", "H30", "H31", "R01", "R02"],
                    ["A市", 100, 200, 300, 400],
                    ["B市", 150, 250, 350, 450],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("年（和暦）" in v.description and "4列" in v.description for v in result.violations)

    def test_mixed_categorical_columns_pass(self, create_context):
        """年以外の複数カテゴリ列は決定論的チェックでは横持ちと判定されない（AI無効時）"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "性別", "年齢", "職業", "住所"],
                        ["太郎", "男", 30, "会社員", "東京"],
                        ["花子", "女", 25, "学生", "大阪"],
                        ["次郎", "男", 40, "公務員", "福岡"],
                    ],
                },
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is True

    def test_prefecture_as_columns_detected_by_ai(self, create_context):
        """47都道府県が列名の横持ちを AI が検出するテスト"""
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "都道府県",
                "details": "47都道府県が列名になっています",
                "confidence": 0.95,
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["指標", "北海道", "青森県", "岩手県", "宮城県", "秋田県"],
                        ["人口", 5228, 1238, 1211, 2303, 966],
                        ["面積", 83424, 9645, 15275, 7282, 11637],
                    ],
                }
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert any("AI検出" in v.description for v in result.violations)
            assert any("都道府県" in v.description for v in result.violations)

    def test_gender_as_columns_detected_by_ai(self, create_context):
        """性別が列名の横持ちを AI が検出するテスト"""
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "性別",
                "details": "男性・女性・不明が列名になっています",
                "confidence": 0.90,
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["年齢区分", "男性", "女性", "不明", "合計"],
                        ["0-4歳", 100, 95, 5, 200],
                        ["5-9歳", 110, 105, 3, 218],
                        ["10-14歳", 120, 115, 2, 237],
                    ],
                }
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert any("AI検出" in v.description for v in result.violations)
            assert any("性別" in v.description for v in result.violations)

    def test_ai_unavailable_time_axis_still_detected(self, create_context):
        """AI unavailable 時も時間軸横持ちは決定論的に検出される"""
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "2019年", "2020年", "2021年", "2022年"],
                        ["太郎", 100, 200, 300, 400],
                        ["花子", 150, 250, 350, 450],
                    ],
                }
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert any("横持ち" in v.description for v in result.violations)
            # AI検出のラベルは付かない
            assert not any("AI検出" in v.description for v in result.violations)

    def test_ai_not_called_when_time_axis_detected(self, create_context):
        """時間軸横持ちが既に検出済みなら AI を呼ばないテスト"""
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "年",
                "details": "年が列名になっています",
                "confidence": 0.99,
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "2019年", "2020年", "2021年", "2022年"],
                        ["太郎", 100, 200, 300, 400],
                        ["花子", 150, 250, 350, 450],
                    ],
                }
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            # 時間軸横持ちは検出されている
            assert result.passed is False
            # AI のチェックは呼ばれていない（時間軸が既に検出済みなので）
            mock_ai.check_wide_format_semantic.assert_not_called()

    def test_ai_low_confidence_not_flagged(self, create_context):
        """AI の confidence が 0.7 未満なら違反にしない"""
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "不明",
                "details": "横持ちかもしれない",
                "confidence": 0.5,  # 低い確信度
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "項目A", "項目B", "項目C", "項目D"],
                        ["太郎", 100, 200, 300, 400],
                        ["花子", 150, 250, 350, 450],
                    ],
                }
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            # 低確信度なら違反にしない
            assert not any("AI検出" in v.description for v in result.violations)


class TestVerticalFormatThresholds:
    """L3-09 判定閾値の境界テスト

    `VerticalFormatRule` の class 定数として宣言された閾値を、コードと
    一緒に動かさないと壊れない形でテスト上に固定する。閾値を変更する場合
    はこのテスト群を意図的に更新すること。
    """

    def test_min_total_cols_boundary_just_below(self, create_context):
        """総列数 MIN_TOTAL_COLS - 1 で「判定対象外」を返す"""
        assert VerticalFormatRule.MIN_TOTAL_COLS == 4
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "2020年", "2021年"],
                    ["太郎", 100, 200],
                    ["花子", 150, 250],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert result.message == "列数が少ないため横持ちの判定対象外"
        assert result.confidence == VerticalFormatRule.CONFIDENCE_SKIPPED_FEW_COLS

    def test_time_axis_below_threshold_not_flagged(self, create_context):
        """時間軸列が MIN_TIME_AXIS_COLS - 1 のときは時間軸ヒューリスティクスで横持ちと判定しない"""
        assert VerticalFormatRule.MIN_TIME_AXIS_COLS == 3
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "性別", "2020年", "2021年"],
                        ["太郎", "男", 100, 200],
                        ["花子", "女", 150, 250],
                    ],
                },
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is True
            assert not any("横持ち" in v.description for v in result.violations)

    def test_time_axis_at_threshold_flagged(self, create_context):
        """時間軸列が MIN_TIME_AXIS_COLS ちょうどで横持ちと判定する"""
        assert VerticalFormatRule.MIN_TIME_AXIS_COLS == 3
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "2020年", "2021年", "2022年"],
                    ["太郎", 100, 200, 300],
                    ["花子", 150, 250, 350],
                ],
            },
        )
        rule = VerticalFormatRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("横持ち" in v.description and "年が3列" in v.description for v in result.violations)

    def test_numbered_columns_below_threshold_not_flagged(self, create_context):
        """類似名称の数値サフィックス列が MIN_NUMBERED_GROUP_SIZE - 1 では info を出さない"""
        assert VerticalFormatRule.MIN_NUMBERED_GROUP_SIZE == 4
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "年齢", "項目1", "項目2", "項目3"],
                        ["太郎", 30, "a", "b", "c"],
                        ["花子", 25, "x", "y", "z"],
                    ],
                },
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is True
            assert not any("類似名称" in v.description for v in result.violations)

    def test_numbered_columns_at_threshold_flagged(self, create_context):
        """類似名称の数値サフィックス列が MIN_NUMBERED_GROUP_SIZE ちょうどで info を出す"""
        assert VerticalFormatRule.MIN_NUMBERED_GROUP_SIZE == 4
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["名前", "項目1", "項目2", "項目3", "項目4"],
                        ["太郎", "a", "b", "c", "d"],
                        ["花子", "x", "y", "z", "w"],
                    ],
                },
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert any("類似名称" in v.description and "4列" in v.description for v in result.violations)

    def test_ai_confidence_at_threshold_flagged(self, create_context):
        """AI confidence が AI_CONFIDENCE_THRESHOLD ちょうどで違反にする"""
        assert VerticalFormatRule.AI_CONFIDENCE_THRESHOLD == 0.7
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "性別",
                "details": "性別が列名になっています",
                "confidence": VerticalFormatRule.AI_CONFIDENCE_THRESHOLD,
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["年齢区分", "男性", "女性", "不明"],
                        ["0-4歳", 100, 95, 5],
                        ["5-9歳", 110, 105, 3],
                    ],
                },
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert any("AI検出" in v.description for v in result.violations)

    def test_ai_confidence_just_below_threshold_not_flagged(self, create_context):
        """AI confidence が AI_CONFIDENCE_THRESHOLD 直下では違反にしない"""
        threshold = VerticalFormatRule.AI_CONFIDENCE_THRESHOLD
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "性別",
                "details": "性別が列名になっています",
                "confidence": threshold - 0.01,
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["年齢区分", "男性", "女性", "不明"],
                        ["0-4歳", 100, 95, 5],
                        ["5-9歳", 110, 105, 3],
                    ],
                },
            )
            rule = VerticalFormatRule()
            result = rule.check(ctx)
            assert not any("AI検出" in v.description for v in result.violations)

    def test_max_total_cols_constant(self):
        """100 列上限が定数として固定されていること"""
        assert VerticalFormatRule.MAX_TOTAL_COLS == 100

    def test_over_max_total_cols_detected_as_error(self, create_context):
        """総列数が MAX_TOTAL_COLS を超えるとき severity='error' の違反を出す"""
        assert VerticalFormatRule.MAX_TOTAL_COLS == 100
        headers = ["項目"] + [f"col{i}" for i in range(1, 101)]  # 計 101 列
        body = ["A"] + list(range(1, 101))
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context({"Sheet1": [headers, body, body]})
            rule = VerticalFormatRule()
            result = rule.check(ctx)
        assert result.passed is False
        error_violation = next(
            (v for v in result.violations if v.severity == "error"),
            None,
        )
        assert error_violation is not None, "101 列のとき error 違反が立つべき"
        assert "101" in error_violation.description
        assert "列" in error_violation.description

    def test_exactly_max_total_cols_does_not_trigger_max_rule(self, create_context):
        """ちょうど MAX_TOTAL_COLS では 100 列ルール由来の error を出さない"""
        assert VerticalFormatRule.MAX_TOTAL_COLS == 100
        # 100 列ぴったり、かつ時間軸/番号付きパターンを発火させないヘッダー名
        headers = [f"列{chr(0x3041 + (i % 80))}{i}" for i in range(100)]
        body = [f"v{i}" for i in range(100)]
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = False
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context({"Sheet1": [headers, body, body]})
            rule = VerticalFormatRule()
            result = rule.check(ctx)
        # 100 列上限ルール由来の error 違反は出ないこと
        assert not any(v.severity == "error" and "列超" in v.description for v in result.violations)

    def test_ai_not_called_when_over_max_total_cols(self, create_context):
        """総列数が MAX_TOTAL_COLS を超えるとき AI を呼ばない"""
        assert VerticalFormatRule.MAX_TOTAL_COLS == 100
        headers = ["項目"] + [f"列{i}" for i in range(1, 101)]  # 101 列
        body = ["A"] + list(range(1, 101))
        with patch("harunobu.rules.level3.L3_09_vertical_format.AISemanticChecker") as MockClass:
            mock_ai = MagicMock()
            mock_ai.is_available.return_value = True
            mock_ai.check_wide_format_semantic.return_value = {
                "is_wide": True,
                "category_type": "X",
                "details": "",
                "confidence": 0.99,
            }
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context({"Sheet1": [headers, body, body]})
            rule = VerticalFormatRule()
            result = rule.check(ctx)
        mock_ai.check_wide_format_semantic.assert_not_called()
        assert any(v.severity == "error" for v in result.violations)
