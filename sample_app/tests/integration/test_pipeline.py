"""統合テスト: パイプライン全体の動作確認"""

from __future__ import annotations

import pytest

from harunobu.core.analyzer import MRChecker, analyze_sheet
from harunobu.core.models import (
    CellRange,
    CheckResult,
    Config,
    MRResult,
    Sheet,
    SheetResult,
    TableLayout,
    TableRegion,
    WorkBook,
)
from harunobu.core.severity import Severity
from harunobu.rules.level1.L1_05_column_headers import ColumnHeadersRule
from harunobu.rules.level1.L1_12_merged_cells import MergedCellsRule
from harunobu.rules.level2.L2_03_unique_headers import UniqueHeadersRule
from harunobu.rules.registry import RuleRegistry, registry


class TestFullPipeline:
    """analyze_sheet を通してパイプライン全体が動作することを確認する。"""

    def test_analyze_sheet_returns_sheet_result(self, create_workbook):
        """シート分析がSheetResultを返す"""
        wb = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["名前", "年齢", "所在地"],
                    ["田中太郎", 30, "東京都"],
                    ["鈴木花子", 25, "大阪府"],
                    ["佐藤一郎", 40, "北海道"],
                ],
            },
        )
        sheet = wb.sheets[0]

        result = analyze_sheet(workbook=wb, sheet=sheet)

        assert isinstance(result, SheetResult)
        assert result.sheet_meta.name == "Sheet1"
        assert result.sheet_meta.used_range != ""
        # テーブルが1つ以上検出される
        assert len(result.tables) >= 1

    def test_analyze_sheet_produces_mr_results(self, create_workbook):
        """analyze_sheetの結果にMRResultが含まれる"""
        wb = create_workbook(
            sheets_data={
                "データ": [
                    ["ID", "品目", "数量", "単価"],
                    [1, "りんご", 100, 200],
                    [2, "みかん", 50, 150],
                ],
            },
        )
        sheet = wb.sheets[0]

        result = analyze_sheet(workbook=wb, sheet=sheet)

        assert len(result.tables) >= 1
        table = result.tables[0]
        # MRResult にレベル1のチェック結果が含まれる
        all_results = table.mr_result.all_results()
        assert len(all_results) > 0
        for _, check in all_results.items():
            assert isinstance(check, CheckResult)
            assert isinstance(check.passed, bool)

    def test_analyze_sheet_with_empty_sheet(self):
        """空シートの場合もエラーなく処理される"""
        sheet = Sheet(name="Empty", cells={}, max_row=0, max_col=0)
        wb = WorkBook(file_name="empty.xlsx", file_format="xlsx", sheets=[sheet])

        result = analyze_sheet(workbook=wb, sheet=sheet)

        assert isinstance(result, SheetResult)
        assert result.sheet_meta.name == "Empty"
        assert len(result.tables) == 0


class TestMRChecker:
    """MRCheckerの単体・統合テスト。"""

    def test_check_all_runs_level1_rules(self, create_context):
        """MRCheckerがLevel1の全ルールを実行する"""
        ctx = create_context(
            sheets_data={
                "Sheet1": [
                    ["名前", "年齢", "住所"],
                    ["田中", 30, "東京都"],
                    ["鈴木", 25, "大阪府"],
                ],
            },
        )

        checker = MRChecker()
        config = Config(mr_levels={1})
        mr_result = checker.check_all(ctx, config)

        assert isinstance(mr_result, MRResult)
        # Level1に15ルール存在する（CSV専用ルールはxlsx対象外なので除外される）
        assert len(mr_result.level1) > 0
        # Level2/3は空
        assert len(mr_result.level2) == 0
        assert len(mr_result.level3) == 0

    def test_check_all_runs_level2_rules(self, create_context):
        """MRCheckerがLevel2のルールも実行する"""
        ctx = create_context(
            sheets_data={
                "Sheet1": [
                    ["コード", "名称", "値"],
                    ["A001", "品目A", 100],
                    ["A002", "品目B", 200],
                ],
            },
        )

        checker = MRChecker()
        config = Config(mr_levels={1, 2})
        mr_result = checker.check_all(ctx, config)

        assert len(mr_result.level1) > 0
        assert len(mr_result.level2) > 0

    def test_check_all_respects_level_config(self, create_context):
        """Config.mr_levelsでルールレベルを制限できる"""
        ctx = create_context(
            sheets_data={
                "Sheet1": [
                    ["A", "B"],
                    [1, 2],
                ],
            },
        )

        checker = MRChecker()

        # Level1のみ
        config_l1 = Config(mr_levels={1})
        result_l1 = checker.check_all(ctx, config_l1)
        assert len(result_l1.level2) == 0
        assert len(result_l1.level3) == 0

        # Level3のみ
        config_l3 = Config(mr_levels={3})
        result_l3 = checker.check_all(ctx, config_l3)
        assert len(result_l3.level1) == 0
        assert len(result_l3.level2) == 0
        assert len(result_l3.level3) > 0

    def test_check_all_respects_custom_rules(self, create_context):
        """Config.custom_rulesで対象ルールを制限できる"""
        ctx = create_context(
            sheets_data={
                "Sheet1": [
                    ["ヘッダ1", "ヘッダ2"],
                    ["値1", "値2"],
                ],
            },
        )

        checker = MRChecker()
        config = Config(mr_levels={1}, custom_rules=["L1-01"])
        mr_result = checker.check_all(ctx, config)

        # 1ルールのみ実行される
        all_results = mr_result.all_results()
        assert len(all_results) <= 1


class TestRuleRegistry:
    """RuleRegistryの統合テスト。"""

    def test_discover_finds_all_30_rules(self):
        """レジストリが30個のルールを発見する"""
        reg = RuleRegistry()
        reg.discover()

        all_rules = reg.get_all()
        assert len(all_rules) == 30, (
            f"期待: 30ルール, 実際: {len(all_rules)}ルール. IDs: {sorted(r.rule_id for r in all_rules)}"
        )

    def test_discover_finds_correct_level_distribution(self):
        """レベルごとに正しい数のルールが登録される"""
        reg = RuleRegistry()
        reg.discover()

        assert len(reg.get_by_level(1)) == 15
        assert len(reg.get_by_level(2)) == 6
        assert len(reg.get_by_level(3)) == 9

    def test_global_registry_works(self):
        """グローバルregistryインスタンスが動作する"""
        # discover済みでなければ実行
        if not registry.get_all():
            registry.discover()

        all_rules = registry.get_all()
        assert len(all_rules) == 30

    def test_get_rule_by_id(self):
        """rule_idでルールを取得できる"""
        reg = RuleRegistry()
        reg.discover()

        rule = reg.get("L1-01")
        assert rule.rule_id == "L1-01"
        assert rule.level == 1

    def test_get_nonexistent_rule_raises(self):
        """存在しないrule_idでKeyErrorが発生する"""
        reg = RuleRegistry()
        reg.discover()

        with pytest.raises(KeyError):
            reg.get("NONEXISTENT-99")


class TestMergedCellsRuleInteraction:
    """L1-05 / L1-12 / L2-03 のセル結合まわりの整合性 E2E テスト。

    設計判断: ヘッダー領域のセル結合は L1 では許容、L2 では一意識別性の観点から許容しない。
    各ルールがこの方針と整合した結果を返すことを確認する。
    """

    @staticmethod
    def _set_header_layout(ctx, header_rows: list[int], body_start: int, body_end: int) -> None:
        """テストコンテキストのヘッダ行を設定する。"""
        ctx.table_region = TableRegion(
            range=CellRange(
                start_row=1,
                start_col=1,
                end_row=ctx.sheet.max_row,
                end_col=ctx.sheet.max_col,
            ),
            layout=TableLayout(
                header_rows=header_rows,
                body_start_row=body_start,
                body_end_row=body_end,
            ),
            confidence=1.0,
        )

    def test_single_row_header_merge_l1_pass_l2_fail(self, create_context):
        """単一行ヘッダーで横結合（タイトル相当） → L1 は許容、L2-03 のみ失敗。

        - 行1: "名前", "住所"(B1:C1 結合)
        - 行2,3: データ

        L2 では結合ヘッダー自体を許容しないため、単一行ヘッダーでも
        結合の従属セル（C1）が違反として検出される。
        """
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "住所", None],
                    ["太郎", "東京", "港区"],
                    ["花子", "大阪", "北区"],
                ]
            },
            merged_cells=[
                {"sheet": "Sheet1", "start_row": 1, "start_col": 2, "end_row": 1, "end_col": 3},
            ],
        )
        self._set_header_layout(ctx, header_rows=[1], body_start=2, body_end=3)

        l1_12 = MergedCellsRule().check(ctx)
        l1_05 = ColumnHeadersRule().check(ctx)
        l2_03 = UniqueHeadersRule().check(ctx)

        # L1-12: ヘッダ領域のみの結合 → 許容
        assert l1_12.passed is True
        assert l1_12.severity == Severity.MAJOR
        # L1-05: マスタ値「住所」で col 2,3 をカバー
        assert l1_05.passed is True
        # L2-03: 単一行ヘッダーでも結合ヘッダーは許容しない → 違反
        assert l2_03.passed is False

    def test_multirow_header_merge_l1_pass_l2_fail(self, create_context):
        """複数行ヘッダーで親行に横結合 → L1 はパス、L2-03 のみ失敗。

        - 行1: "個人情報"(A1:B1 結合), C1="住所"
        - 行2: "名前", "年齢", None
        - 行3-: データ
        """
        ctx = create_context(
            {
                "Sheet1": [
                    ["個人情報", None, "住所"],
                    ["名前", "年齢", None],
                    ["太郎", 20, "東京"],
                    ["花子", 25, "大阪"],
                ]
            },
            merged_cells=[
                {"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 1, "end_col": 2},
            ],
        )
        self._set_header_layout(ctx, header_rows=[1, 2], body_start=3, body_end=4)

        l1_12 = MergedCellsRule().check(ctx)
        l1_05 = ColumnHeadersRule().check(ctx)
        l2_03 = UniqueHeadersRule().check(ctx)

        # L1-12: ヘッダ領域の結合のみ → 許容
        assert l1_12.passed is True
        assert l1_12.severity == Severity.MAJOR
        # L1-05: 全列に有効なヘッダーあり（row1 のマスタ or row2 の値）
        assert l1_05.passed is True
        # L2-03: 親行（row1）の横結合により col 2 の連結が不完全 → 違反
        assert l2_03.passed is False

    def test_body_merge_l1_12_fail_l1_05_l2_03_pass(self, create_context):
        """データ領域の結合 → L1-12 のみ失敗、L1-05/L2-03 はパス。

        - 行1: ヘッダ "名前", "年齢", "住所"
        - 行2: データ、A2:B2 結合
        - 行3-: データ
        """
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年齢", "住所"],
                    ["合計", None, "100"],
                    ["太郎", 20, "東京"],
                    ["花子", 25, "大阪"],
                ]
            },
            merged_cells=[
                {"sheet": "Sheet1", "start_row": 2, "start_col": 1, "end_row": 2, "end_col": 2},
            ],
        )
        self._set_header_layout(ctx, header_rows=[1], body_start=2, body_end=4)

        l1_12 = MergedCellsRule().check(ctx)
        l1_05 = ColumnHeadersRule().check(ctx)
        l2_03 = UniqueHeadersRule().check(ctx)

        # L1-12: データ領域の結合 → 違反、FATAL
        assert l1_12.passed is False
        assert l1_12.severity == Severity.FATAL
        # L1-05: ヘッダ行に問題なし
        assert l1_05.passed is True
        # L2-03: ヘッダに結合なし → 一意性 OK
        assert l2_03.passed is True

    def test_full_pipeline_with_header_merge_passes_l1_12(self, create_workbook):
        """analyze_sheet を経由した本格的なパイプラインでも、ヘッダ結合は L1-12 でパスする。

        IslandDetector が header_rows を含む layout を構築 → L1-12 が動的 severity=MAJOR を設定。
        """
        wb = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["都道府県", "人口", None],
                    [None, "2020年", "2021年"],
                    ["北海道", 5000, 4950],
                    ["青森", 1200, 1180],
                    ["岩手", 1180, 1160],
                ],
            },
            merged_cells=[
                {"sheet": "Sheet1", "start_row": 1, "start_col": 2, "end_row": 1, "end_col": 3},
            ],
        )
        sheet = wb.sheets[0]
        result = analyze_sheet(workbook=wb, sheet=sheet)

        assert len(result.tables) >= 1
        all_results = result.tables[0].mr_result.all_results()
        assert "L1-12" in all_results
        l1_12 = all_results["L1-12"]
        # ヘッダ領域の結合のみのケース → passed=True、severity=MAJOR
        assert l1_12.passed is True
        assert l1_12.severity == Severity.MAJOR
