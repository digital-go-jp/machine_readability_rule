"""L3-07 bulk チェックのテスト."""

from __future__ import annotations

import pytest

from harunobu.core.analyzer import Analyzer
from harunobu.rules.level3.L3_07_format_consistency import FormatConsistencyRule


def _make_workbook(create_workbook, file_name: str, headers: list[str], rows: int = 5):
    data = [headers]
    for i in range(rows):
        data.append([i + 1] + [f"v{i}" for _ in headers[1:]])
    return create_workbook(sheets_data={"Sheet1": data}, file_name=file_name)


def test_bulk_same_schema_passes(create_workbook):
    """同一スキーマの 3 ファイルは bulk チェック PASS."""
    headers = ["年度", "都道府県", "件数", "金額"]
    wbs = [_make_workbook(create_workbook, f"data_R{i}.xlsx", headers) for i in (3, 4, 5)]

    analyzer = Analyzer(mode="thorough")
    bulk_result = analyzer.analyze_bulk(wbs)

    assert bulk_result.file_count == 3
    assert "L3-07" in bulk_result.bulk_checks
    bulk_check = bulk_result.bulk_checks["L3-07"]
    assert bulk_check.passed, f"Expected pass, got violations: {bulk_check.violations}"


def test_bulk_different_columns_detected(create_workbook):
    """列数が違うファイルが混在すると違反検出."""
    wb1 = _make_workbook(create_workbook, "data_R3.xlsx", ["年度", "都道府県", "件数"])
    wb2 = _make_workbook(create_workbook, "data_R4.xlsx", ["年度", "都道府県", "件数"])
    wb3 = _make_workbook(
        create_workbook,
        "data_R5.xlsx",
        ["年度", "都道府県", "件数", "金額", "件数A", "件数B", "件数C"],
    )

    analyzer = Analyzer(mode="thorough")
    bulk_result = analyzer.analyze_bulk([wb1, wb2, wb3])

    assert "L3-07" in bulk_result.bulk_checks
    bulk_check = bulk_result.bulk_checks["L3-07"]
    assert not bulk_check.passed
    assert any("列数" in v.description for v in bulk_check.violations)


def test_bulk_header_set_diverges(create_workbook):
    """ヘッダー集合が大きく異なるファイル群で違反検出."""
    wb1 = _make_workbook(create_workbook, "data_R3.xlsx", ["年度", "都道府県", "件数", "金額"])
    wb2 = _make_workbook(create_workbook, "data_R4.xlsx", ["年", "県", "数", "額"])

    analyzer = Analyzer(mode="thorough")
    bulk_result = analyzer.analyze_bulk([wb1, wb2])

    bulk_check = bulk_result.bulk_checks["L3-07"]
    assert not bulk_check.passed
    assert any("Jaccard" in v.description or "ヘッダー集合" in v.description for v in bulk_check.violations)


def test_bulk_rule_runs_in_standard_mode(create_workbook):
    """standard モード（mr_levels={1,2}）でも bulk ルールは実行される.

    複数ファイルアップロードはユーザーが横断評価を明示的に要求した状況なので、
    mr_levels のフィルタリングは bulk ルールには適用されない。
    """
    wb1 = _make_workbook(create_workbook, "data_R3.xlsx", ["年度", "件数"])
    wb2 = _make_workbook(create_workbook, "data_R4.xlsx", ["年度", "件数"])

    analyzer = Analyzer(mode="standard")
    bulk_result = analyzer.analyze_bulk([wb1, wb2])

    assert "L3-07" in bulk_result.bulk_checks


def test_bulk_single_file_skipped(create_workbook):
    """1 ファイルだけなら bulk フェーズはスキップされる."""
    wb = _make_workbook(create_workbook, "only.xlsx", ["年度", "都道府県", "件数"])

    analyzer = Analyzer(mode="thorough")
    bulk_result = analyzer.analyze_bulk([wb])

    assert bulk_result.file_count == 1
    assert bulk_result.bulk_checks == {} or all(
        cr.message.startswith("bulk") for cr in bulk_result.bulk_checks.values()
    )


def test_check_bulk_direct_call():
    """ルールの check_bulk を直接呼んでも動作する."""
    rule = FormatConsistencyRule()
    # 空のファイルリストでも 1 件以下は skip
    result = rule.check_bulk([])
    assert result.passed
    assert "スキップ" in result.message


def test_bulk_missing_headers_reported_as_warning():
    """ヘッダー抽出に失敗したファイルは silently drop せず warning で報告する."""
    from harunobu.core.models import AnalysisResult, FileMeta
    from harunobu.rules.bulk_base import BulkFileEntry

    def _entry(name: str) -> BulkFileEntry:
        meta = FileMeta(name=name, size=0, format="xlsx", sheet_count=0)
        return BulkFileEntry(
            file_name=name,
            file_meta=meta,
            workbook=None,
            analysis=AnalysisResult(file_meta=meta, sheets=[]),
        )

    rule = FormatConsistencyRule()
    result = rule.check_bulk([_entry("a.xlsx"), _entry("b.xlsx")])

    descriptions = " ".join(v.description for v in result.violations)
    assert "a.xlsx" in descriptions and "b.xlsx" in descriptions
    assert any(v.severity == "warning" for v in result.violations)
    assert not result.passed


@pytest.mark.parametrize(
    "headers_per_file,expected_pass",
    [
        ([["A", "B"], ["A", "B"]], True),
        ([["A", "B", "C", "D"], ["B", "A", "C", "D"]], False),  # 順序変動
    ],
)
def test_bulk_order_change(create_workbook, headers_per_file, expected_pass):
    """共通ヘッダーの並び順が変動すると違反検出."""
    wbs = [_make_workbook(create_workbook, f"data_R{i}.xlsx", headers) for i, headers in enumerate(headers_per_file)]
    analyzer = Analyzer(mode="thorough")
    bulk_result = analyzer.analyze_bulk(wbs)

    bulk_check = bulk_result.bulk_checks["L3-07"]
    assert bulk_check.passed == expected_pass
