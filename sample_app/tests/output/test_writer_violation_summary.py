"""csv_writer / json_writer の違反要約表示テスト

VIOLATIONS_DISPLAY_LIMIT を超えた CheckResult を含む AnalysisResult に対して
各 writer が要約出力（グループベース）を行うことを検証する。
"""

from __future__ import annotations

import json

from harunobu.core.models import (
    VIOLATIONS_DISPLAY_LIMIT,
    AnalysisResult,
    CellRange,
    CheckResult,
    FileMeta,
    MRResult,
    SheetMeta,
    SheetResult,
    TableLayout,
    TableResult,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.output import csv_writer, json_writer

# ─── CSV カラムインデックス（位置依存を避けるためカラム名から解決） ───

_COL_COUNT = csv_writer.HEADER.index("違反数")
_COL_LOCS = csv_writer.HEADER.index("違反箇所")
_COL_DESCS = csv_writer.HEADER.index("違反内容")

# ─── ヘルパ ───


def _violation(
    sheet: str = "Sheet1",
    cell_range: str = "A1",
    severity: str = "error",
) -> Violation:
    return Violation(  # type: ignore[arg-type]
        sheet=sheet,
        cell_range=cell_range,
        description=f"{sheet} の違反: {cell_range}",
        severity=severity,
    )


def _make_analysis(violations: list[Violation]) -> AnalysisResult:
    """単一ルール・単一テーブルの AnalysisResult を生成する。"""
    cr = CheckResult(
        rule_id="L1-12",
        passed=False,
        severity=Severity.MAJOR,
        confidence=1.0,
        violations=violations,
    )
    mr = MRResult(level1={"L1-12": cr})
    table = TableResult(
        range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
        confidence=0.95,
        mr_result=mr,
    )
    sheet = SheetResult(
        sheet_meta=SheetMeta(name="Sheet1", used_range="A1:E10"),
        tables=[table],
    )
    return AnalysisResult(
        file_meta=FileMeta(name="test.xlsx", size=1024, format="xlsx", sheet_count=1),
        sheets=[sheet],
    )


def _few_violations() -> list[Violation]:
    """閾値以下の違反リスト（全件展開されるべき）。"""
    return [_violation(cell_range=f"A{i}") for i in range(5)]


def _many_violations() -> list[Violation]:
    """閾値超の違反リスト（要約表示されるべき）。"""
    return [_violation(cell_range=f"A{i}") for i in range(VIOLATIONS_DISPLAY_LIMIT + 10)]


# ─── csv_writer ───


class TestCsvWriterViolationSummary:
    def _get_data_row(self, result: AnalysisResult) -> list[str]:
        rows = csv_writer.to_rows(result)
        # rows[0] はヘッダー、rows[1] がデータ行
        assert len(rows) == 2
        return rows[1]

    def test_few_violations_shows_individual_locations(self) -> None:
        result = _make_analysis(_few_violations())
        row = self._get_data_row(result)
        violation_locs = row[_COL_LOCS]
        # 個別セル範囲が "!" を含む形式で出力される
        assert "A0!A0" not in violation_locs  # 誤形式でないこと
        assert "Sheet1!A0" in violation_locs

    def test_many_violations_shows_summary_in_locations(self) -> None:
        result = _make_analysis(_many_violations())
        row = self._get_data_row(result)
        violation_locs = row[_COL_LOCS]
        # 「計 N 件」という要約文字列が含まれる
        assert f"計 {VIOLATIONS_DISPLAY_LIMIT + 10} 件" in violation_locs

    def test_many_violations_shows_group_summary_in_descs(self) -> None:
        result = _make_analysis(_many_violations())
        row = self._get_data_row(result)
        violation_descs = row[_COL_DESCS]
        # "Sheet1/error: N件" 形式のグループサマリが出力される
        assert "Sheet1/error" in violation_descs
        assert "件" in violation_descs

    def test_violation_count_column_always_shows_total(self) -> None:
        """「違反数」列は要約の有無に関わらず実件数を返す。"""
        few = _make_analysis(_few_violations())
        many = _make_analysis(_many_violations())
        few_row = csv_writer.to_rows(few)[1]
        many_row = csv_writer.to_rows(many)[1]
        assert few_row[_COL_COUNT] == "5"
        assert many_row[_COL_COUNT] == str(VIOLATIONS_DISPLAY_LIMIT + 10)

    def test_few_violations_no_summary_marker(self) -> None:
        """閾値以下では「他」「計」という要約マーカーが出ない。"""
        result = _make_analysis(_few_violations())
        row = self._get_data_row(result)
        violation_locs = row[_COL_LOCS]
        assert "他" not in violation_locs
        assert "計" not in violation_locs

    def test_multigroup_summary_lists_all_groups(self) -> None:
        """複数 (sheet, severity) グループがある場合、全グループが列挙される。"""
        violations = [_violation(sheet="Sheet1", severity="error", cell_range=f"A{i}") for i in range(15)] + [
            _violation(sheet="Sheet1", severity="warning", cell_range=f"B{i}") for i in range(10)
        ]
        result = _make_analysis(violations)
        row = csv_writer.to_rows(result)[1]
        violation_descs = row[_COL_DESCS]
        assert "Sheet1/error" in violation_descs
        assert "Sheet1/warning" in violation_descs


# ─── json_writer ───


class TestJsonWriterViolationSummary:
    def _get_check_dict(self, result: AnalysisResult) -> dict:
        raw = json_writer.to_json(result)
        data = json.loads(raw)
        # sheets[0]["評価対象エリア"][0]["評価内容"][0]
        return data["sheets"][0]["評価対象エリア"][0]["評価内容"][0]

    def test_few_violations_is_list(self) -> None:
        result = _make_analysis(_few_violations())
        check_dict = self._get_check_dict(result)
        assert isinstance(check_dict["違反"], list)
        assert len(check_dict["違反"]) == 5

    def test_few_violations_has_no_violation_group_field(self) -> None:
        """閾値以下では「違反グループ」フィールドが存在しない。"""
        result = _make_analysis(_few_violations())
        check_dict = self._get_check_dict(result)
        assert "違反グループ" not in check_dict

    def test_many_violations_violations_field_is_still_list(self) -> None:
        """閾値超過時も「違反」は生の Violation リストのまま（後方互換）。"""
        result = _make_analysis(_many_violations())
        check_dict = self._get_check_dict(result)
        assert isinstance(check_dict["違反"], list)
        assert len(check_dict["違反"]) == VIOLATIONS_DISPLAY_LIMIT + 10

    def test_many_violations_has_violation_group_field(self) -> None:
        """閾値超過時に「違反グループ」フィールドが付与される。"""
        result = _make_analysis(_many_violations())
        check_dict = self._get_check_dict(result)
        assert "違反グループ" in check_dict
        summary = check_dict["違反グループ"]
        assert summary["合計件数"] == VIOLATIONS_DISPLAY_LIMIT + 10
        assert isinstance(summary["グループ"], list)
        assert len(summary["グループ"]) >= 1

    def test_many_violations_group_fields_complete(self) -> None:
        """「違反グループ」各グループに必須フィールドが揃っている。"""
        result = _make_analysis(_many_violations())
        check_dict = self._get_check_dict(result)
        g = check_dict["違反グループ"]["グループ"][0]
        assert "シート" in g
        assert "重大度" in g
        assert "件数" in g
        assert "代表セル範囲" in g

    def test_many_violations_group_counts_sum_to_total(self) -> None:
        result = _make_analysis(_many_violations())
        check_dict = self._get_check_dict(result)
        summary = check_dict["違反グループ"]
        total_from_groups = sum(g["件数"] for g in summary["グループ"])
        assert total_from_groups == summary["合計件数"]

    def test_empty_violations_is_empty_list(self) -> None:
        result = _make_analysis([])
        check_dict = self._get_check_dict(result)
        assert check_dict["違反"] == []
        assert "違反グループ" not in check_dict

    def test_multigroup_json_has_correct_sheet_and_severity(self) -> None:
        violations = [_violation(sheet="Sheet1", severity="error", cell_range=f"A{i}") for i in range(15)] + [
            _violation(sheet="Sheet2", severity="warning", cell_range=f"B{i}") for i in range(10)
        ]
        result = _make_analysis(violations)
        check_dict = self._get_check_dict(result)
        groups = check_dict["違反グループ"]["グループ"]
        sheets_in_groups = {g["シート"] for g in groups}
        assert "Sheet1" in sheets_in_groups
        assert "Sheet2" in sheets_in_groups
