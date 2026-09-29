"""L2-01: 数値データは数値属性とし、文字列を含まないことのテスト"""

from harunobu.rules.level2.L2_01_numeric_purity import NumericPurityRule


class TestNumericPurityCheck:
    """L2-01 数値内文字列混在チェック"""

    def test_pure_numeric_passes(self, create_context):
        """数値のみのデータで違反なし"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], [100, 200], [300, 400]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_unit_mixed_in_numeric(self, create_context):
        """数値に単位が混在している場合に違反を検出（数値列のみ）"""
        # col2は数値が多い列なので "200円" は違反として検出される
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["100人", 500], [300, 400], [200, 600]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert any("単位" in v.description for v in result.violations)

    def test_unit_mixed_in_numeric_column_majority(self, create_context):
        """数値列（>50%が数値）で単位混在を検出"""
        # col2: 200円, 400, 600 → 数値的セルが3つ中3つ (200円も数値的)、
        # 200円は単位混在として検出される
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", "200円"], ["B", 400], ["C", 600]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("単位" in v.description for v in result.violations)

    def test_note_mixed_in_numeric(self, create_context):
        """数値に注釈（括弧付き）が混在している場合に違反を検出"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", "100（暫定）"], ["B", 200], ["C", 300]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("注釈" in v.description for v in result.violations)

    def test_pure_numeric_string_passes(self, create_context):
        """純粋な数値文字列（カンマ付き等）は違反にならない"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["1,234", "5,678"], ["100", "200"]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_non_numeric_column_skipped(self, create_context):
        """テキスト主体の列はチェック対象外"""
        # col1は全て文字列 → 数値列ではないのでスキップ
        ctx = create_context(
            {"Sheet1": [["名前", "値"], ["田中100人", 200], ["山田200件", 300], ["佐藤", 400]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        # col1はテキスト主体なので違反なし
        assert result.passed is True

    def test_pure_text_cells_in_numeric_column_not_flagged(self, create_context):
        """数値列内の完全テキストセルは違反にならない"""
        # col2: "合計なし", 200, 300 → 2/3が数値 → 数値列
        # "合計なし" は完全テキストなのでスキップ
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", "合計なし"], ["B", 200], ["C", 300]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_percentage_column_not_flagged(self, create_context):
        """パーセント列のパーセント値は違反にならない"""
        ctx = create_context(
            {"Sheet1": [["項目", "割合"], ["A", "50%"], ["B", "30%"], ["C", "20%"]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_percentage_in_non_percentage_column_flagged(self, create_context):
        """非パーセント列でパーセント値は違反"""
        # col2: 100, 200, "30%" → 数値列だがパーセント列ではない
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", 100], ["B", 200], ["C", "30%"]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "単位" in result.violations[0].description

    def test_fullwidth_percentage_column_not_flagged(self, create_context):
        """全角パーセント列のパーセント値も違反にならない"""
        ctx = create_context(
            {"Sheet1": [["項目", "割合"], ["A", "50％"], ["B", "30％"], ["C", "20％"]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_numbered_label_in_numeric_column_flagged(self, create_context):
        """数値列に混入した番号付きラベルは違反として検出される"""
        # 従来は _NUMBERED_LABEL で除外していたが、数値列に現れた場合は違反
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["1①.所在地", 500], [300, 400], [200, 600]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_low_digit_ratio_text_in_numeric_column_flagged(self, create_context):
        """数値列に混入した数字率の低いテキストは違反として検出される"""
        # 従来は digit ratio < 30% でスキップしていたが、数値列に現れた場合は違反
        ctx = create_context(
            {"Sheet1": [["項目", "金額"], ["平成30年度", 500], [300, 400], [200, 600]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_pure_text_missing_value_in_numeric_column_allowed(self, create_context):
        """数字を含まない純粋テキスト（欠損値マーカー）は数値列でも許容される"""
        # 「合計なし」「欠損」等は統計表での欠損表現として許容
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", "合計なし"], ["B", 200], ["C", 300]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_triangle_prefix_string_flagged(self, create_context):
        """▲△▼ 付き文字列は違反として検出される（文字列型のまま入力されている場合）"""
        # ▲3,000 / △3,000 / ▼3,000 は文字列であり数値属性ではないため違反
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", "▲3,000"], ["B", 500], ["C", 600]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1

    def test_triangle_prefix_numeric_allowed(self, create_context):
        """セル値が int/float の場合は ▲ 等の書式表示でも違反にならない"""
        # openpyxl data_only で読み込んだ場合、書式設定の ▲ は剥がれて -3000 (int) になる
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["A", -3000], ["B", 500], ["C", 600]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_header_cells_not_flagged(self, create_context):
        """ヘッダー行はチェックされない"""
        # ヘッダーに "100人" があっても違反にならない
        ctx = create_context(
            {"Sheet1": [["100人", "値"], [100, 200], [300, 400]]},
        )
        rule = NumericPurityRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
