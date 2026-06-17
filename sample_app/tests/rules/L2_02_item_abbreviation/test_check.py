"""L2-02: データ内での項目名等の省略をしていないかのテスト"""

from unittest.mock import MagicMock, patch

from harunobu.rules.level2.L2_02_item_abbreviation import ItemAbbreviationRule


class TestItemAbbreviationCheck:
    """L2-02 行ヘッダー（stub_cols）の省略チェック"""

    def test_no_abbreviation_passes(self, create_context):
        """行ヘッダーに省略記号も空白もない場合は違反なし"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "名前", "値"],
                    ["A", "太郎", 100],
                    ["B", "花子", 200],
                    ["C", "次郎", 300],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_abbreviation_marker_detected(self, create_context):
        """行ヘッダー内の省略記号（〃、同上等）の使用を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "名前", "値"],
                    ["A", "太郎", 100],
                    ["〃", "花子", 200],
                    ["同上", "次郎", 300],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) >= 2
        assert any("省略記号" in v.description for v in result.violations)

    def test_consecutive_empty_detected(self, create_context):
        """行ヘッダーで連続する空白セルによる省略を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "値"],
                    ["A", 100],
                    ["", 200],
                    ["", 300],
                    ["", 400],
                    ["B", 500],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is False
        empty_violations = [v for v in result.violations if "欠落" in v.description]
        # 連続 3 つの空白すべてが違反になる
        assert len(empty_violations) == 3

    def test_single_empty_flagged_when_prev_value_exists(self, create_context):
        """行ヘッダーでは前に値があれば単一の空白でも違反として検出する"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "値"],
                    ["A", 100],
                    ["", 200],
                    ["B", 300],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is False
        empty_violations = [v for v in result.violations if "欠落" in v.description]
        assert len(empty_violations) == 1

    def test_trailing_empty_flagged(self, create_context):
        """行ヘッダー末尾の空白も「前に値あり」なら違反として検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "名前"],
                    ["A", "太郎"],
                    ["", "花子"],
                    ["", "次郎"],
                    ["", "四郎"],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        empty_violations = [v for v in result.violations if "欠落" in v.description]
        # 末尾の 3 連続空白もすべて違反扱い
        assert len(empty_violations) == 3

    def test_column_start_empty_not_flagged(self, create_context):
        """行ヘッダー列の先頭から続く空白は違反としない（多階層ヘッダー考慮）"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "備考"],
                    ["", "メモ1"],
                    ["", "メモ2"],
                    ["", "メモ3"],
                    ["A", "メモ4"],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        empty_violations = [v for v in result.violations if "欠落" in v.description]
        assert len(empty_violations) == 0

    def test_non_stub_column_not_checked(self, create_context):
        """行ヘッダー以外の列にある空白や省略記号は検出対象外"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "備考"],
                    ["A", "メモ"],
                    ["B", ""],
                    ["C", "〃"],
                    ["D", ""],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        # col=1（カテゴリ）には欠落も省略記号もない
        assert result.passed is True
        assert len(result.violations) == 0

    def test_abbreviation_marker_in_stub_column(self, create_context):
        """行ヘッダー列内の省略記号を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "値"],
                    ["A", 100],
                    ["〃", 200],
                    ["C", 300],
                ],
            },
            stub_cols=[1],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("省略記号" in v.description for v in result.violations)

    def test_empty_stub_cols_is_skipped(self, create_context):
        """stub_cols が空のときは判定対象外（confidence=0）"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "値"],
                    ["A", 100],
                    ["", 200],
                    ["", 300],
                ],
            },
            stub_cols=[],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert result.confidence == 0.0
        assert result.is_skipped is True
        assert len(result.violations) == 0

    def test_multiple_stub_cols(self, create_context):
        """複数の行ヘッダー列をすべて検査"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["大区分", "小区分", "値"],
                    ["甲", "X", 100],
                    ["甲", "", 200],
                    ["〃", "Y", 300],
                ],
            },
            stub_cols=[1, 2],
        )
        rule = ItemAbbreviationRule()
        result = rule.check(ctx)
        assert result.passed is False
        # col=2 の空白（前に X あり）と col=1 の 〃 がともに検出される
        assert any("欠落" in v.description for v in result.violations)
        assert any("省略記号" in v.description for v in result.violations)

    def test_ai_abbreviation_detection_wareki(self, create_context):
        """AIが和暦略称（H28, H29）を行ヘッダー列内の省略として検出するテスト"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.check_abbreviations.return_value = [
            {"row": 3, "col": 1, "value": "H29", "reason": "和暦略称 H28 の繰り返し省略"}
        ]
        with patch("harunobu.rules.level2.L2_02_item_abbreviation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {"Sheet1": [["年度", "値"], ["H28", 100], ["H29", 200], ["H30", 300]]},
                stub_cols=[1],
            )
            rule = ItemAbbreviationRule()
            result = rule.check(ctx)
            assert len(result.violations) >= 1
            assert any("AI検出" in v.description for v in result.violations)

    def test_ai_unavailable_fallback_still_detects_markers(self, create_context):
        """AI unavailable 時も既存マーカー（〃等）を検出する"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        with patch("harunobu.rules.level2.L2_02_item_abbreviation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["カテゴリ", "名前", "値"],
                        ["A", "太郎", 100],
                        ["〃", "花子", 200],
                        ["同上", "次郎", 300],
                    ]
                },
                stub_cols=[1],
            )
            rule = ItemAbbreviationRule()
            result = rule.check(ctx)
            assert result.passed is False
            assert len(result.violations) >= 2
            assert any("省略記号" in v.description for v in result.violations)
            # AI unavailable 時は confidence が 0.70
            assert result.confidence == 0.70

    def test_ai_check_only_called_for_stub_columns(self, create_context):
        """AI チェックは行ヘッダー列に対してのみ呼ばれる"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.check_abbreviations.return_value = []
        with patch("harunobu.rules.level2.L2_02_item_abbreviation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {
                    "Sheet1": [
                        ["カテゴリ", "金額", "備考"],
                        ["A", 100, "メモ1"],
                        ["B", 200, "メモ2"],
                        ["C", 300, "メモ3"],
                    ]
                },
                stub_cols=[1],
            )
            rule = ItemAbbreviationRule()
            rule.check(ctx)
            # stub 列以外（金額、備考）には check_abbreviations が呼ばれない
            for call in mock_ai.check_abbreviations.call_args_list:
                args, kwargs = call
                header_arg = args[1] if len(args) > 1 else kwargs.get("header", "")
                assert header_arg in ("カテゴリ", ""), f"stub 列以外（{header_arg}）に対して AI が呼ばれた"

    def test_ai_not_called_when_stub_cols_empty(self, create_context):
        """stub_cols が空のときは AI チェックも呼ばれない"""
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = True
        mock_ai.check_abbreviations.return_value = []
        with patch("harunobu.rules.level2.L2_02_item_abbreviation.AISemanticChecker") as MockClass:
            MockClass.get_instance.return_value = mock_ai
            ctx = create_context(
                {"Sheet1": [["カテゴリ", "値"], ["A", 100], ["B", 200]]},
                stub_cols=[],
            )
            rule = ItemAbbreviationRule()
            rule.check(ctx)
            mock_ai.check_abbreviations.assert_not_called()
