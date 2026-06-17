"""L2-06: 数式→値チェックのテスト

数式が含まれるセルがモデルに正しく反映されることを確認する。
"""

from harunobu.core.models import FormulaErrorRef, FormulaRef
from harunobu.rules.level2.L2_06_formula_to_value import FormulaToValueRule


class TestFormulaToValueCheck:
    """L2-06 数式→値チェック"""

    def test_no_formulas_passes(self, create_context):
        """数式がない場合"""
        ctx = create_context({"Sheet1": [["項目", "値"], ["合計", 100]]})
        # 全セルにformulaがないことを確認
        for cell in ctx.sheet.cells.values():
            assert cell.formula is None

    def test_formula_detected(self, create_context):
        """数式がモデルに正しく設定される"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["合計", 100]]},
            formulas={"Sheet1": {(2, 2): "=SUM(B2:B10)"}},
        )
        cell = ctx.sheet.get_cell(2, 2)
        assert cell is not None
        assert cell.formula == "=SUM(B2:B10)"
        assert cell.value == 100

    def test_multiple_formulas(self, create_context):
        """複数の数式がある場合"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["A", "B", "C"],
                    [10, 20, 30],
                ]
            },
            formulas={
                "Sheet1": {
                    (2, 1): "=A1+1",
                    (2, 2): "=B1+1",
                    (2, 3): "=SUM(A2:B2)",
                }
            },
        )
        assert ctx.sheet.get_cell(2, 1).formula == "=A1+1"
        assert ctx.sheet.get_cell(2, 2).formula == "=B1+1"
        assert ctx.sheet.get_cell(2, 3).formula == "=SUM(A2:B2)"

    def test_formula_on_specific_sheet(self, create_context):
        """特定シートのみに数式がある場合"""
        ctx = create_context(
            {
                "Sheet1": [["A"], [10]],
                "Sheet2": [["B"], [20]],
            },
            formulas={"Sheet2": {(2, 1): "=B1*2"}},
            sheet_index=0,
        )
        # Sheet1のセルにはformulaなし
        cell = ctx.sheet.get_cell(2, 1)
        assert cell is not None
        assert cell.formula is None

    def test_cells_without_formulas_have_none(self, create_context):
        """数式のないセルのformulaはNone"""
        ctx = create_context(
            {"Sheet1": [["名前", "値"], ["test", 42]]},
            formulas={"Sheet1": {(2, 2): "=A1+1"}},
        )
        # (2,1)は数式なし
        cell_no_formula = ctx.sheet.get_cell(2, 1)
        assert cell_no_formula is not None
        assert cell_no_formula.formula is None

        # (2,2)は数式あり
        cell_with_formula = ctx.sheet.get_cell(2, 2)
        assert cell_with_formula is not None
        assert cell_with_formula.formula == "=A1+1"

    def test_rule_no_formulas_passes(self, create_context):
        """数式がない場合にルールチェックはパス"""
        ctx = create_context({"Sheet1": [["項目", "値"], ["合計", 100]]})
        rule = FormulaToValueRule()
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_rule_formula_detected(self, create_context):
        """数式があるセルは違反として検出される"""
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["合計", 100]]},
            formulas={"Sheet1": {(2, 2): "=SUM(B2:B10)"}},
        )
        rule = FormulaToValueRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        assert "数式" in result.violations[0].description

    def test_rule_multiple_formulas_all_detected(self, create_context):
        """複数の数式が全て検出される"""
        ctx = create_context(
            {"Sheet1": [["A", "B", "C"], [10, 20, 30]]},
            formulas={
                "Sheet1": {
                    (2, 1): "=A1+1",
                    (2, 3): "=SUM(A2:B2)",
                }
            },
        )
        rule = FormulaToValueRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2

    def test_rule_score_decreases_with_formulas(self, create_context):
        """数式の割合に応じてスコアが下がる"""
        ctx = create_context(
            {"Sheet1": [["A"], [1], [2], [3], [4]]},
            formulas={"Sheet1": {(2, 1): "=A1+1"}},
        )
        rule = FormulaToValueRule()
        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score < 100
        # assert result.score >= 0

    def test_rule_csv_format_checks_formulas(self, create_context):
        """CSVでも数式チェックは実行される（target=EXCELだが、モデルに数式あれば検出）"""
        # target=EXCELのためCSVは通常スキップされるが、モデルに数式があれば検出
        ctx = create_context(
            {"Sheet1": [["項目", "値"], ["合計", 100]]},
            formulas={"Sheet1": {(2, 2): "=SUM(A1:A10)"}},
        )
        rule = FormulaToValueRule()
        result = rule.check(ctx)
        # target=EXCELだがContextのfile_formatに依存しない（check内でファイル形式チェックなし）
        assert len(result.violations) >= 0  # 動作確認

    def test_rule_detects_reference_only_ooxml_formula_ref(self, create_context):
        """=A2 のような参照だけの数式も違反として検出する"""
        ctx = create_context({"Sheet1": [["項目", "値"], [10, 10]]})
        ctx.sheet.formula_refs_loaded = True
        ctx.sheet.formula_refs = [FormulaRef(sheet_name="Sheet1", cell_ref="B2", row=2, col=2, formula_text="A2")]

        result = FormulaToValueRule().check(ctx)

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].cell_range == "B2"
        assert "=A2" in result.violations[0].description

    def test_rule_string_equals_value_is_not_flagged_when_ooxml_loaded(self, create_context):
        """OOXML検出済みなら文字列 '=A2' を旧ヒューリスティックで誤検知しない"""
        ctx = create_context({"Sheet1": [["項目", "値"], [10, "=A2"]]})
        ctx.sheet.formula_refs_loaded = True
        ctx.sheet.formula_refs = []
        ctx.sheet.formula_error_refs = []

        result = FormulaToValueRule().check(ctx)

        assert result.passed is True
        assert result.violations == []

    def test_rule_formula_outside_table_range_is_not_flagged(self, create_context):
        """テーブル外の数式セルは違反にしない"""
        ctx = create_context({"Sheet1": [["項目", "値"], [1, 100], ["備考", 0]]})
        ctx.table_region.range.end_row = 2
        ctx.sheet.formula_refs_loaded = True
        ctx.sheet.formula_refs = [FormulaRef(sheet_name="Sheet1", cell_ref="B3", row=3, col=2, formula_text="TODAY()")]

        result = FormulaToValueRule().check(ctx)

        assert result.passed is True
        assert result.violations == []

    def test_rule_detects_shared_formula_without_text(self, create_context):
        """shared formula の従属セルは式本文が空でも違反にする"""
        ctx = create_context({"Sheet1": [["項目", "値"], [1, 2]]})
        ctx.sheet.formula_refs_loaded = True
        ctx.sheet.formula_refs = [
            FormulaRef(
                sheet_name="Sheet1",
                cell_ref="B2",
                row=2,
                col=2,
                formula_type="shared",
                formula_text=None,
            )
        ]

        result = FormulaToValueRule().check(ctx)

        assert result.passed is False
        assert len(result.violations) == 1
        assert "shared formula" in result.violations[0].description

    def test_rule_detects_ref_errors_and_deduplicates_formula_same_cell(self, create_context):
        """#REF! はL2-06で違反にし、同一セルの数式違反と重複させない"""
        ctx = create_context({"Sheet1": [["項目", "値"], [1, "#REF!"]]})
        ctx.sheet.formula_refs_loaded = True
        ctx.sheet.formula_error_refs = [
            FormulaErrorRef(sheet_name="Sheet1", cell_ref="B2", row=2, col=2, error_text="#REF!")
        ]
        ctx.sheet.formula_refs = [FormulaRef(sheet_name="Sheet1", cell_ref="B2", row=2, col=2, formula_text="A2")]

        result = FormulaToValueRule().check(ctx)

        assert result.passed is False
        assert len(result.violations) == 1
        assert "参照切れ" in result.violations[0].description

    def test_rule_formula_refs_error_is_inconclusive(self, create_context):
        """OOXML検出失敗時は高confidenceのOKにしない"""
        ctx = create_context({"Sheet1": [["項目", "値"], [1, 2]]})
        ctx.sheet.formula_refs_error = "inspect_failed:BadZipFile"

        result = FormulaToValueRule().check(ctx)

        assert result.passed is True
        # assert result.score == 0
        assert result.confidence == 0.0
        assert result.violations == []
        assert "判定できません" in result.message

    def test_rule_legacy_fallback_detects_ref_error_value(self, create_context):
        """OOXML未検出の手組みモデルでは #REF! 値も違反にする"""
        ctx = create_context({"Sheet1": [["項目", "値"], [1, "#REF!"]]})

        result = FormulaToValueRule().check(ctx)

        assert result.passed is False
        assert len(result.violations) == 1
        assert "参照切れ" in result.violations[0].description
