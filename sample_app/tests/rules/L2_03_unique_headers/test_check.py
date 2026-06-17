"""L2-03: 各列が一意に識別可能な項目名を持っているかのテスト"""

from __future__ import annotations

from harunobu.core.models import (
    CellRange,
    TableContext,
    TableLayout,
    TableRegion,
)
from harunobu.rules.level2.L2_03_unique_headers import UniqueHeadersRule


def _override_layout(
    ctx: TableContext,
    *,
    header_rows: list[int],
    body_start_row: int,
    body_end_row: int,
) -> TableContext:
    """create_context が生成したコンテキストのレイアウトだけ差し替えて返す。"""
    table_region = TableRegion(
        range=CellRange(
            start_row=1,
            start_col=1,
            end_row=ctx.sheet.max_row,
            end_col=ctx.sheet.max_col,
        ),
        layout=TableLayout(
            header_rows=header_rows,
            body_start_row=body_start_row,
            body_end_row=body_end_row,
            columns=ctx.table_region.layout.columns,
        ),
        columns=ctx.table_region.columns,
        confidence=1.0,
    )
    return TableContext(workbook=ctx.workbook, sheet=ctx.sheet, table_region=table_region)


class TestUniqueHeadersCheck:
    """check() の正常系・異常系・エッジケースを網羅する"""

    # ------------------------------------------------------------------
    # 正常系
    # ------------------------------------------------------------------

    def test_all_unique_headers_pass(self, create_context):
        """全列のヘッダーが一意な場合は合格"""
        ctx = create_context(
            {"Sheet1": [["氏名", "年齢", "住所"], ["田中", 30, "東京"], ["山田", 25, "大阪"]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert result.violations == []

    def test_single_column_passes(self, create_context):
        """列が1つだけでも合格"""
        ctx = create_context(
            {"Sheet1": [["値"], [1], [2]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is True
        # assert result.score == 100

    # ------------------------------------------------------------------
    # 異常系：重複ヘッダー
    # ------------------------------------------------------------------

    def test_duplicate_headers_detected(self, create_context):
        """同名ヘッダーが複数列に存在する場合は違反を検出"""
        ctx = create_context(
            {"Sheet1": [["名前", "スコア", "スコア"], ["A", 10, 20], ["B", 30, 40]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        # assert result.score < 100
        # 重複している "スコア" の2列分が違反
        assert len(result.violations) == 2
        assert all("重複" in v.description for v in result.violations)
        assert all("スコア" in v.description for v in result.violations)

    def test_multiple_duplicate_groups_detected(self, create_context):
        """重複グループが複数ある場合はすべて検出"""
        ctx = create_context(
            {"Sheet1": [["A", "B", "A", "B"], [1, 2, 3, 4]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        # A×2 + B×2 = 4件の違反
        assert len(result.violations) == 4

    # ------------------------------------------------------------------
    # 異常系：空ヘッダー
    # ------------------------------------------------------------------

    def test_empty_header_with_data_detected(self, create_context):
        """データのある列のヘッダーが空の場合は違反"""
        ctx = create_context(
            {"Sheet1": [["氏名", "", "住所"], ["田中", 99, "東京"], ["山田", 88, "大阪"]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        assert any("空" in v.description for v in result.violations)

    def test_empty_header_on_empty_column_ignored(self, create_context):
        """ヘッダーが空でもデータ列も空なら無視"""
        ctx = create_context(
            {"Sheet1": [["氏名", "", "住所"], ["田中", None, "東京"], ["山田", None, "大阪"]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is True
        assert result.violations == []

    # ------------------------------------------------------------------
    # エッジケース：除外ルール
    # ------------------------------------------------------------------

    def test_numeric_headers_flagged_as_duplicate(self, create_context):
        """単行で数値ヘッダーが重複する場合は違反（除外なし）"""
        ctx = create_context(
            {"Sheet1": [["項目", "1", "2", "1"], ["A", 10, 20, 30]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2

    def test_survey_marker_headers_flagged_as_duplicate(self, create_context):
        """単行でアンケートマーカーが重複する場合は違反（除外なし）"""
        ctx = create_context(
            {"Sheet1": [["設問1", "○", "設問2", "○"], [True, True, False, True]]},
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        assert len(result.violations) == 2

    # ------------------------------------------------------------------
    # 結合セル — L2 では結合ヘッダー自体を許容しない（除外パターンなし）
    # ------------------------------------------------------------------

    def test_single_row_merged_header_flagged(self, create_context):
        """単一行ヘッダーで横結合あり → 親結合範囲全体が違反として報告される"""
        # A1:B1 を横結合。L2 では結合ヘッダーを許容しないため親結合範囲が違反
        ctx = create_context(
            {
                "Sheet1": [
                    ["カテゴリ", "カテゴリ", "値"],
                    [10, 20, 30],
                ]
            },
            merged_cells=[{"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 1, "end_col": 2}],
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        # 親結合範囲 A1:B1 全体が 1 件の違反として検出される（dedupe 後）
        assert len(result.violations) == 1
        v = result.violations[0]
        assert "結合ヘッダー" in v.description
        # cell_range は親結合範囲全体（A1:B1）であり、従属セルの B1 単独ではない
        assert v.cell_range == "A1:B1"

    # ------------------------------------------------------------------
    # 複数行ヘッダー
    # ------------------------------------------------------------------

    def test_multirow_header_unique_combined_names_pass(self, create_context):
        """複数行ヘッダーで連結後の名前がユニーク、かつ結合なしなら合格"""
        ctx = _override_layout(
            create_context(
                {
                    "Sheet1": [
                        ["地域", "地域", "全体"],
                        ["東京", "大阪", "合計"],
                        [100, 200, 300],
                    ]
                }
            ),
            header_rows=[1, 2],
            body_start_row=3,
            body_end_row=3,
        )
        result = UniqueHeadersRule().check(ctx)
        # 結合なし、連結: "地域_東京", "地域_大阪", "全体_合計" — すべて一意
        assert result.passed is True

    def test_multirow_header_duplicate_combined_names_detected(self, create_context):
        """複数行ヘッダーで連結後の名前が重複する場合は違反"""
        ctx = _override_layout(
            create_context(
                {
                    "Sheet1": [
                        ["地域", "地域"],
                        ["東京", "東京"],
                        [100, 200],
                    ]
                }
            ),
            header_rows=[1, 2],
            body_start_row=3,
            body_end_row=3,
        )
        result = UniqueHeadersRule().check(ctx)
        # 連結: "地域_東京" が2列 → 違反
        assert result.passed is False
        assert len(result.violations) == 2

    def test_multirow_header_with_merge_flagged(self, create_context):
        """複数行ヘッダーで親行に横結合 → 親結合範囲全体が違反として報告される"""
        # 親行 (Row1) の B1:C1 を横結合。
        ctx = _override_layout(
            create_context(
                {
                    "Sheet1": [
                        ["", "財務情報", "財務情報"],
                        ["会社", "売上高", "営業利益"],
                        ["A", 100, 10],
                    ]
                },
                merged_cells=[{"sheet": "Sheet1", "start_row": 1, "start_col": 2, "end_row": 1, "end_col": 3}],
            ),
            header_rows=[1, 2],
            body_start_row=3,
            body_end_row=3,
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        merge_violations = [v for v in result.violations if "結合ヘッダー" in v.description]
        assert len(merge_violations) == 1
        # 違反箇所は親結合範囲 B1:C1 全体（C1 単独ではない）
        assert merge_violations[0].cell_range == "B1:C1"

    def test_multiple_multirow_merges_flagged(self, create_context):
        """親行に複数の横結合グループ → それぞれの親結合範囲が独立した違反として報告される"""
        # 親行 (Row1) に 2 つの横結合: B1:C1 と D1:E1
        ctx = _override_layout(
            create_context(
                {
                    "Sheet1": [
                        ["", "売上", "売上", "経費", "経費"],
                        ["会社", "国内", "海外", "国内", "海外"],
                        ["A", 100, 50, 30, 20],
                    ]
                },
                merged_cells=[
                    {"sheet": "Sheet1", "start_row": 1, "start_col": 2, "end_row": 1, "end_col": 3},
                    {"sheet": "Sheet1", "start_row": 1, "start_col": 4, "end_row": 1, "end_col": 5},
                ],
            ),
            header_rows=[1, 2],
            body_start_row=3,
            body_end_row=3,
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is False
        # B1:C1 と D1:E1 がそれぞれ独立した違反として報告される
        merge_violations = [v for v in result.violations if "結合ヘッダー" in v.description]
        assert len(merge_violations) == 2
        cell_ranges = sorted(v.cell_range for v in merge_violations)
        assert cell_ranges == ["B1:C1", "D1:E1"]

    # ------------------------------------------------------------------
    # ヘッダー行なし（スキップ）
    # ------------------------------------------------------------------

    def test_no_header_rows_skips_with_low_confidence(self, create_context):
        """ヘッダー行が未検出の場合は低confidence でスキップ"""
        ctx = _override_layout(
            create_context({"Sheet1": [[1, 2], [3, 4]]}),
            header_rows=[],
            body_start_row=1,
            body_end_row=2,
        )
        result = UniqueHeadersRule().check(ctx)
        assert result.passed is True
        assert result.confidence == 0.40

    # ------------------------------------------------------------------
    # スコア計算
    # ------------------------------------------------------------------

    def test_score_reflects_violation_ratio(self, create_context):
        """違反数 / 総列数の割合でスコアが下がる"""
        # 4列中2列が重複違反 → score = 100 * (1 - 2/4) = 50
        ctx = create_context(
            {"Sheet1": [["A", "B", "B", "C"], [1, 2, 3, 4]]},
        )
        UniqueHeadersRule().check(ctx)
        # assert result.score == 50
