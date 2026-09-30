"""L1-14: CSVデータ内改行チェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.core.models import CellRange, Config, TableContext, TableLayout, TableRegion
from harunobu.core.reader import read_file
from harunobu.rules.level1.L1_14_csv_single_line import CsvSingleLineRule


def _csv_context(path):
    workbook = read_file(path)
    sheet = workbook.sheets[0]
    table_region = TableRegion(
        range=CellRange(start_row=1, start_col=1, end_row=sheet.max_row, end_col=sheet.max_col),
        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=sheet.max_row),
        confidence=1.0,
    )
    return TableContext(workbook=workbook, sheet=sheet, table_region=table_region, config=Config())


class TestCsvSingleLineCheck:
    """L1-14 CSVデータ内改行チェック"""

    @pytest.fixture
    def rule(self):
        return CsvSingleLineRule()

    def test_no_newlines_passes(self, rule, create_context):
        """raw診断がないCSV fixtureはチェックをスキップする"""
        ctx = create_context(
            {"Sheet1": [["名前", "住所"], ["太郎", "東京都千代田区"]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert result.confidence == 0.0
        assert len(result.violations) == 0
        assert "raw診断情報がない" in result.message

    def test_xlsx_skipped(self, rule, create_context):
        """Excel形式の場合はチェック対象外"""
        ctx = create_context(
            {"Sheet1": [["名前", "住所"], ["太郎", "東京都\n千代田区"]]},
            file_name="test.xlsx",
        )
        result = rule.check(ctx)
        assert result.passed is True

    def test_raw_diagnostics_missing_does_not_use_cell_value_fallback(self, rule, create_context):
        """パース済みセル値の改行だけではL1-14違反にしない"""
        ctx = create_context(
            {"Sheet1": [["名前", "住所"], ["太郎", "東京都\n千代田区"]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True
        assert result.confidence == 0.0
        assert result.violations == []

    def test_quoted_comma_from_reader_passes(self, rule, tmp_path):
        """正しくクォートされたカンマ入りフィールドはL1-14では問題にしない"""
        csv_path = tmp_path / "quoted_comma.csv"
        csv_path.write_text('id,name,value\n1,"Tokyo, Japan",100\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is True

    def test_quoted_newline_from_reader_fails_with_physical_lines(self, rule, tmp_path):
        """正しくクォートされた改行でも1行1データ違反として説明する"""
        csv_path = tmp_path / "quoted_newline.csv"
        csv_path.write_text('id,comment,value\n1,"hello\nworld",100\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert len(result.violations) == 1
        description = result.violations[0].description
        assert "論理行2" in description
        assert "物理行2-3" in description

    def test_unclosed_quote_from_reader_fails(self, rule, tmp_path):
        """quote閉じ忘れで複数物理行にまたがる場合もL1-14でfail"""
        csv_path = tmp_path / "unclosed.csv"
        csv_path.write_text('id,comment\n1,"unclosed\n2,next\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert "quote" in result.violations[0].description.lower() or "クォート" in result.violations[0].description

    def test_truncated_diagnostics_still_fail_with_summary(self, rule, tmp_path, monkeypatch):
        """大量改行違反で診断が打ち切られても代表例と集約messageでfailする"""
        monkeypatch.setattr("harunobu.core.reader.MAX_CSV_ISSUES_BEFORE_ABORT", 2)
        csv_path = tmp_path / "many_multiline.csv"
        csv_path.write_text(
            'id,comment\n1,"a\nb"\n2,"c\nd"\n3,"e\nf"\n4,ok\n',
            encoding="utf-8",
        )
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert "打ち切" in result.message
