"""L1-15: CSVクォーティングチェックのテスト"""

from __future__ import annotations

import pytest

from harunobu.core.models import CellRange, Config, TableContext, TableLayout, TableRegion
from harunobu.core.reader import read_file
from harunobu.rules.level1.L1_15_csv_quoting import CsvQuotingRule


def _csv_context(path):
    workbook = read_file(path)
    sheet = workbook.sheets[0]
    table_region = TableRegion(
        range=CellRange(start_row=1, start_col=1, end_row=sheet.max_row, end_col=sheet.max_col),
        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=sheet.max_row),
        confidence=1.0,
    )
    return TableContext(workbook=workbook, sheet=sheet, table_region=table_region, config=Config())


class TestCsvQuotingCheck:
    """L1-15 CSVクォーティングチェック"""

    @pytest.fixture
    def rule(self):
        return CsvQuotingRule()

    def test_no_special_chars_passes(self, rule, create_context):
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
            {"Sheet1": [["名前", "住所"], ["太郎", "東京都,千代田区"]]},
            file_name="test.xlsx",
        )
        result = rule.check(ctx)
        assert result.passed is True

    def test_raw_diagnostics_missing_does_not_use_cell_value_fallback(self, rule, create_context):
        """パース済みセル値の特殊文字だけではL1-15違反にしない"""
        ctx = create_context(
            {"Sheet1": [["名前", "住所"], ["太郎", "東京都,千代田区"]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True
        assert result.confidence == 0.0
        assert result.violations == []

    def test_quoted_comma_from_reader_passes(self, rule, tmp_path):
        """正しくクォートされたカンマ入りフィールドはpass"""
        csv_path = tmp_path / "quoted_comma.csv"
        csv_path.write_text('id,name,value\n1,"Tokyo, Japan",100\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is True
        assert result.violations == []

    def test_escaped_quote_from_reader_passes(self, rule, tmp_path):
        """CSV標準のdouble quote escapeはpass"""
        csv_path = tmp_path / "escaped_quote.csv"
        csv_path.write_text('id,comment\n1,"He said ""OK"""\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is True

    def test_unquoted_comma_field_count_mismatch_is_warning(self, rule, tmp_path):
        """未クォートカンマによる列数崩れ疑いはwarning"""
        csv_path = tmp_path / "bad_comma.csv"
        csv_path.write_text("id,name,value\n1,Tokyo, Japan,100\n2,Osaka,200\n", encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert result.violations[0].severity == "warning"
        assert "基準列数3" in result.violations[0].description

    def test_last_row_unquoted_comma_is_detected(self, rule, tmp_path):
        """最後の行だけの列数崩れ疑いも検出する"""
        csv_path = tmp_path / "last_bad.csv"
        rows = ["id,name,value"]
        rows.extend(f"{i},Name {i},{i}" for i in range(1, 20))
        rows.append("20,Tokyo, Japan,100")
        csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert result.violations[0].severity == "warning"
        assert "論理行21" in result.violations[0].description

    def test_unquoted_double_quote_is_error(self, rule, tmp_path):
        """英文中の未クォートdouble quoteはerror"""
        csv_path = tmp_path / "unquoted_quote.csv"
        csv_path.write_text('id,comment\n1,He said "OK"\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert result.violations[0].severity == "error"
        assert result.violations[0].cell_range == "B2"

    def test_unclosed_quote_is_error(self, rule, tmp_path):
        """quote閉じ忘れはerror"""
        csv_path = tmp_path / "unclosed.csv"
        csv_path.write_text('id,comment\n1,"unclosed\n2,next\n', encoding="utf-8")
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert result.violations[0].severity == "error"
        assert "閉じ" in result.violations[0].description or "quote" in result.violations[0].description.lower()

    def test_tsv_comma_from_reader_not_flagged(self, rule, tmp_path):
        """TSVではカンマはクォート対象外"""
        tsv_path = tmp_path / "comma.tsv"
        tsv_path.write_text("id\tname\tvalue\n1\tTokyo, Japan\t100\n", encoding="utf-8")
        result = rule.check(_csv_context(tsv_path))
        assert result.passed is True

    def test_many_unquoted_quotes_are_summarized_after_truncation(self, rule, tmp_path, monkeypatch):
        """大量の未クォートquoteは全Violation化せず集約する"""
        monkeypatch.setattr("harunobu.core.reader.MAX_CSV_ISSUES_BEFORE_ABORT", 3)
        monkeypatch.setattr("harunobu.core.reader.MAX_CSV_ISSUE_SAMPLES", 2)
        csv_path = tmp_path / "many_quotes.csv"
        csv_path.write_text(
            'id,comment\n1,He said "A"\n2,He said "B"\n3,He said "C"\n4,He said "D"\n',
            encoding="utf-8",
        )
        result = rule.check(_csv_context(csv_path))
        assert result.passed is False
        assert len(result.violations) == 2
        assert "少なくとも4件" in result.message
        assert "打ち切" in result.message


class TestCsvTargetFiltering:
    """CSV/Excel ターゲットフィルタリングの統合テスト"""

    @pytest.fixture
    def rule_14(self):
        return CsvQuotingRule()

    def test_rule_target_is_csv(self):
        """L1-14, L1-15のtargetがCSVであること"""
        from harunobu.rules.base import TargetFormat
        from harunobu.rules.level1.L1_14_csv_single_line import CsvSingleLineRule

        assert CsvSingleLineRule.target == TargetFormat.CSV
        assert CsvQuotingRule.target == TargetFormat.CSV

    def test_csv_rules_included_for_csv_format(self, create_context):
        """CSV形式の場合、CSV専用ルールが実行される"""
        from harunobu.core.analyzer import MRChecker
        from harunobu.core.models import Config

        ctx = create_context(
            {"Sheet1": [["A", "B"], ["1", "2"]]},
            file_name="test.csv",
        )
        checker = MRChecker()
        result = checker.check_all(ctx, Config(mr_levels=[1]))
        assert "L1-14" in result.level1
        assert "L1-15" in result.level1

    def test_csv_rules_excluded_for_xlsx_format(self, create_context):
        """Excel形式の場合、CSV専用ルールが実行されない"""
        from harunobu.core.analyzer import MRChecker
        from harunobu.core.models import Config

        ctx = create_context(
            {"Sheet1": [["A", "B"], ["1", "2"]]},
            file_name="test.xlsx",
        )
        checker = MRChecker()
        result = checker.check_all(ctx, Config(mr_levels=[1]))
        assert "L1-14" not in result.level1
        assert "L1-15" not in result.level1
