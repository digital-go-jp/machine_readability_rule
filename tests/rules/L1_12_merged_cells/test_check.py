"""L1-12: セル結合チェックのテスト

ヘッダ領域の結合は L1 では許容（passed=True, severity=MAJOR, info Violation）。
データ領域の結合は違反（passed=False, severity=FATAL, error Violation）。
両方混在する場合はデータ領域違反を優先（passed=False, severity=FATAL）。
"""

from __future__ import annotations

import pytest

from harunobu.core.severity import Severity
from harunobu.rules.level1.L1_12_merged_cells import MergedCellsRule


class TestMergedCellsCheck:
    """L1-12 セル結合チェック"""

    @pytest.fixture
    def rule(self):
        return MergedCellsRule()

    def test_no_merged_cells_passes(self, rule, create_context):
        """結合セルがない場合、違反なし、severity は注入されない（None のまま）"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        assert len(ctx.sheet.merged_cells) == 0
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
        # check() 内で severity を明示設定しないので None
        # （MRChecker 経由ならクラス属性 CRITICAL が注入される）
        assert result.severity is None

    def test_merged_cells_model_propagation(self, create_context):
        """結合セルが context のモデルに正しく反映される（fixture 動作確認）"""
        ctx = create_context(
            {"Sheet1": [["タイトル", "", ""], ["名前", "年齢", "住所"]]},
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 1,
                    "start_col": 1,
                    "end_row": 1,
                    "end_col": 3,
                }
            ],
        )
        assert len(ctx.sheet.merged_cells) == 1
        mr = ctx.sheet.merged_cells[0]
        assert mr.start_row == 1
        assert mr.start_col == 1
        assert mr.end_row == 1
        assert mr.end_col == 3

    def test_merged_cells_is_merged_flag(self, create_context):
        """結合セルの is_merged フラグが正しく設定される（fixture 動作確認）"""
        ctx = create_context(
            {"Sheet1": [["A", "B", "C"], ["D", "E", "F"]]},
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 1,
                    "start_col": 1,
                    "end_row": 1,
                    "end_col": 2,
                }
            ],
        )
        cell_a1 = ctx.sheet.get_cell(1, 1)
        cell_b1 = ctx.sheet.get_cell(1, 2)
        cell_c1 = ctx.sheet.get_cell(1, 3)

        assert cell_a1 is not None
        assert cell_a1.is_merged is True
        assert cell_b1 is not None
        assert cell_b1.is_merged is True
        assert cell_b1.merge_master is not None
        assert cell_b1.merge_master.row == 1
        assert cell_b1.merge_master.col == 1
        assert cell_c1 is not None
        assert cell_c1.is_merged is False

    # ─── ヘッダ領域の結合: 許容（passed=True, severity=MAJOR, info Violation） ───

    def test_header_only_merge_passes_with_major_severity(self, rule, create_context):
        """ヘッダ領域のみの結合は L1 では許容され、severity=MAJOR が設定される"""
        ctx = create_context(
            {"Sheet1": [["タイトル", "", ""], ["名前", "年齢", "住所"], ["太郎", 20, "東京"]]},
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 1,
                    "start_col": 1,
                    "end_row": 1,
                    "end_col": 3,
                }
            ],
        )
        result = rule.check(ctx)
        assert result.passed is True
        assert result.severity == Severity.MAJOR
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.severity == "info"
        assert "ヘッダ領域" in v.description
        assert "L1では許容" in result.message

    def test_multiple_header_merges_all_pass(self, rule, create_context):
        """複数のヘッダ領域結合があっても passed=True"""
        rows = [["H" + str(c) for c in range(10)]]
        for i in range(9):
            rows.append([f"d{i}_{c}" for c in range(10)])
        ctx = create_context(
            {"Sheet1": rows},
            merged_cells=[
                {"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 1, "end_col": 2},
                {"sheet": "Sheet1", "start_row": 1, "start_col": 3, "end_row": 1, "end_col": 4},
                {"sheet": "Sheet1", "start_row": 1, "start_col": 5, "end_row": 1, "end_col": 6},
                {"sheet": "Sheet1", "start_row": 1, "start_col": 7, "end_row": 1, "end_col": 8},
            ],
        )
        result = rule.check(ctx)
        assert result.passed is True
        assert result.severity == Severity.MAJOR
        assert len(result.violations) == 4
        assert all(v.severity == "info" for v in result.violations)

    # ─── データ領域の結合: 違反（passed=False, severity=FATAL, error Violation） ───

    def test_data_merge_sets_fatal_severity(self, rule, create_context):
        """データ領域の結合は passed=False、severity=FATAL"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢", "住所"], ["合計", "", "100"]]},
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 2,
                    "start_col": 1,
                    "end_row": 2,
                    "end_col": 2,
                }
            ],
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert result.severity == Severity.FATAL
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.severity == "error"
        assert "データ領域" in v.description

    # ─── 混在: データ違反を優先 ───

    def test_mixed_header_and_data_merges(self, rule, create_context):
        """ヘッダとデータ両方に結合がある場合、passed=False、severity=FATAL"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["タイトル", "", ""],
                    ["名前", "年齢", "住所"],
                    ["合計", "", "100"],
                ]
            },
            merged_cells=[
                {
                    "sheet": "Sheet1",
                    "start_row": 1,
                    "start_col": 1,
                    "end_row": 1,
                    "end_col": 3,
                },
                {
                    "sheet": "Sheet1",
                    "start_row": 3,
                    "start_col": 1,
                    "end_row": 3,
                    "end_col": 2,
                },
            ],
        )
        result = rule.check(ctx)
        assert result.passed is False
        assert result.severity == Severity.FATAL
        assert len(result.violations) == 2
        severities = {v.severity for v in result.violations}
        assert "info" in severities  # header merge
        assert "error" in severities  # data merge
        assert "ヘッダ領域1件" in result.message
        assert "データ領域1件" in result.message

    def test_csv_format_skipped(self, rule, create_context):
        """CSV形式はチェック対象外"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
