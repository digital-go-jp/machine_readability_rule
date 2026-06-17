"""L3-01: 項目名行から始まり、次行からデータ入力がされているかのテスト"""

from harunobu.core.models import (
    CellRange,
    Config,
    TableContext,
    TableLayout,
    TableRegion,
)
from harunobu.core.severity import Severity
from harunobu.rules.level3.L3_01_header_start_position import HeaderStartPositionRule


def _build_context(workbook, *, start_row, end_row, end_col, header_rows, body_start_row, body_end_row):
    sheet = workbook.sheets[0]
    table_region = TableRegion(
        range=CellRange(start_row=start_row, start_col=1, end_row=end_row, end_col=end_col),
        layout=TableLayout(
            header_rows=header_rows,
            body_start_row=body_start_row,
            body_end_row=body_end_row,
        ),
        confidence=1.0,
    )
    return TableContext(
        workbook=workbook,
        sheet=sheet,
        table_region=table_region,
        config=Config(),
    )


class TestHeaderStartPositionCheck:
    """L3-01 ヘッダー開始位置チェック"""

    def test_header_at_row1_passes(self, create_context):
        """ヘッダーが1行目から始まる場合に違反なし"""
        ctx = create_context(
            {"Sheet1": [["名前", "値"], ["太郎", 100], ["花子", 200]]},
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
        # passed のときはルール側で severity を明示せず、MRChecker 側で注入される想定
        assert result.severity is None

    def test_title_row_before_header_detected(self, create_workbook):
        """タイトル行がヘッダー前にある場合に違反を検出（FATAL）"""
        workbook = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["統計データ一覧", "", ""],
                    ["", "", ""],
                    ["名前", "年齢", "住所"],
                    ["太郎", 30, "東京"],
                    ["花子", 25, "大阪"],
                ],
            },
        )
        ctx = _build_context(
            workbook,
            start_row=3,
            end_row=5,
            end_col=3,
            header_rows=[3],
            body_start_row=4,
            body_end_row=5,
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert result.severity == Severity.FATAL
        assert any("ファイル先頭行から表が始まっていません" in v.description for v in result.violations)
        assert all(v.severity == "error" for v in result.violations)

    def test_leading_blank_only_is_flagged(self, create_workbook):
        """先頭行が完全な空行のみのケースも違反として扱う（L3 厳格判定）。

        ``table_start_row > 1`` 自体を違反条件とするため、先頭にタイトル等の
        非データ内容がなく完全な空行であっても、ヘッダーが 2 行目から始まる
        場合は FATAL 違反となる。
        """
        workbook = create_workbook(
            sheets_data={
                "Sheet1": [
                    [None, None, None],  # 完全な空行
                    ["名前", "年齢", "住所"],
                    ["太郎", 30, "東京"],
                    ["花子", 25, "大阪"],
                ],
            },
        )
        ctx = _build_context(
            workbook,
            start_row=2,
            end_row=4,
            end_col=3,
            header_rows=[2],
            body_start_row=3,
            body_end_row=4,
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert result.severity == Severity.FATAL
        pre_table_violations = [
            v for v in result.violations if "ファイル先頭行から表が始まっていません" in v.description
        ]
        assert pre_table_violations, "先頭空行のみのケースで pre-table 違反を検出できていません"
        assert all(v.severity == "error" for v in pre_table_violations)
        # cell_range は A1 を含む（範囲は A1 から開始）
        assert any("A1" in v.cell_range for v in pre_table_violations)

    def test_multi_header_rows_detected(self, create_workbook):
        """3行以上の多段ヘッダーを検出（MAJOR）"""
        workbook = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["大分類", "", ""],
                    ["中分類", "", ""],
                    ["小分類", "", ""],
                    ["太郎", 30, "東京"],
                ],
            },
        )
        ctx = _build_context(
            workbook,
            start_row=1,
            end_row=4,
            end_col=3,
            header_rows=[1, 2, 3],
            body_start_row=4,
            body_end_row=4,
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        assert result.passed is False
        # 多段ヘッダーのみは MAJOR（強制 0 点ではない）
        assert result.severity == Severity.MAJOR
        assert any("またがっています" in v.description for v in result.violations)
        # 多段ヘッダー単独の Violation.severity は info
        multi_header_v = [v for v in result.violations if "またがっています" in v.description]
        assert all(v.severity == "info" for v in multi_header_v)

    def test_two_row_header_passes(self, create_workbook):
        """2行ヘッダーは多段ヘッダー違反にならない（3行以上が対象）"""
        workbook = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["大分類", ""],
                    ["小分類", "小分類"],
                    ["データ1", 100],
                    ["データ2", 200],
                ],
            },
        )
        ctx = _build_context(
            workbook,
            start_row=1,
            end_row=4,
            end_col=2,
            header_rows=[1, 2],
            body_start_row=3,
            body_end_row=4,
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        # 2行ヘッダーは許容
        multi_header_violations = [v for v in result.violations if "またがっています" in v.description]
        assert len(multi_header_violations) == 0
        assert result.passed is True
        assert result.severity is None

    def test_empty_row_between_header_and_data_detected(self, create_workbook):
        """ヘッダーとデータの間に空行がある場合を検出（FATAL）"""
        workbook = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["名前", "値"],
                    [None, None],  # 空行
                    ["太郎", 100],
                    ["花子", 200],
                ],
            },
        )
        ctx = _build_context(
            workbook,
            start_row=1,
            end_row=4,
            end_col=2,
            header_rows=[1],
            body_start_row=3,  # 空行をスキップしてデータ開始
            body_end_row=4,
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert result.severity == Severity.FATAL
        assert any("空行" in v.description for v in result.violations)

    def test_multiple_violations_fatal_takes_precedence(self, create_workbook):
        """FATAL と MAJOR が共存する場合は FATAL を採用"""
        workbook = create_workbook(
            sheets_data={
                "Sheet1": [
                    ["タイトル"],
                    ["大分類", "", ""],
                    ["中分類", "", ""],
                    ["小分類", "", ""],
                    ["太郎", 30, "東京"],
                ],
            },
        )
        ctx = _build_context(
            workbook,
            start_row=2,
            end_row=5,
            end_col=3,
            header_rows=[2, 3, 4],
            body_start_row=5,
            body_end_row=5,
        )
        rule = HeaderStartPositionRule()
        result = rule.check(ctx)
        assert result.passed is False
        # 2件以上の違反（pre-table + 多段ヘッダー）
        assert len(result.violations) >= 2
        # FATAL 優位
        assert result.severity == Severity.FATAL
        assert result.effective_severity == Severity.FATAL
