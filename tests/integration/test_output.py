"""統合テスト: JSON/CSV出力の動作確認"""

from __future__ import annotations

import csv
import io
import json

from harunobu.core.models import (
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
from harunobu.output import csv_writer, json_writer


def _make_analysis_result(
    *,
    file_name: str = "test.xlsx",
    sheet_name: str = "Sheet1",
    rules: dict[str, CheckResult] | None = None,
) -> AnalysisResult:
    """テスト用AnalysisResultを生成するヘルパー。"""
    if rules is None:
        rules = {
            "L1-01": CheckResult(
                rule_id="L1-01",
                passed=True,
                confidence=1.0,
                message="ファイル形式は適切です",
            ),
            "L1-12": CheckResult(
                rule_id="L1-12",
                passed=False,
                confidence=0.9,
                message="結合セルが検出されました",
                violations=[
                    Violation(
                        sheet=sheet_name,
                        cell_range="A1:C1",
                        description="セル結合が使用されています",
                        severity="error",
                    ),
                ],
            ),
        }

    mr_result = MRResult(level1=rules)

    return AnalysisResult(
        file_meta=FileMeta(
            name=file_name,
            size=1024,
            format="xlsx",
            sheet_count=1,
        ),
        sheets=[
            SheetResult(
                sheet_meta=SheetMeta(name=sheet_name, used_range="A1:E10"),
                tables=[
                    TableResult(
                        range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
                        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
                        confidence=0.95,
                        mr_result=mr_result,
                    ),
                ],
            ),
        ],
    )


def _make_skipped_and_normal_result() -> AnalysisResult:
    """判定対象外ルールと通常ルールを含むAnalysisResult。"""
    return _make_analysis_result(
        rules={
            "L3-02": CheckResult(rule_id="L3-02", passed=True, confidence=0, message="判定対象外"),
            "L1-01": CheckResult(rule_id="L1-01", passed=True, confidence=1.0, message="OK"),
        }
    )


class TestJsonOutput:
    """JSON出力の統合テスト。"""

    def test_to_json_produces_valid_json(self):
        """to_jsonが有効なJSON文字列を返す"""
        result = _make_analysis_result()
        json_str = json_writer.to_json(result)

        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_json_has_japanese_keys(self):
        """JSONに日本語キーが含まれる"""
        result = _make_analysis_result()
        parsed = json.loads(json_writer.to_json(result))

        assert "inputファイル名" in parsed
        assert "Sheet数" in parsed
        assert "レベル別スコア" in parsed
        assert "sheets" in parsed

    def test_json_contains_file_name(self):
        """JSONにファイル名が含まれる"""
        result = _make_analysis_result(file_name="報告書.xlsx")
        parsed = json.loads(json_writer.to_json(result))

        assert parsed["inputファイル名"] == "報告書.xlsx"

    def test_json_contains_sheet_results(self):
        """JSONにシート結果が含まれる"""
        result = _make_analysis_result()
        parsed = json.loads(json_writer.to_json(result))

        sheets = parsed["sheets"]
        assert len(sheets) == 1
        assert sheets[0]["シート名"] == "Sheet1"

    def test_json_contains_rule_results(self):
        """JSONにルール結果が含まれる"""
        result = _make_analysis_result()
        parsed = json.loads(json_writer.to_json(result))

        evaluations = parsed["sheets"][0]["評価対象エリア"][0]["評価内容"]
        assert len(evaluations) == 2

        rule_ids = {e["ルールID"] for e in evaluations}
        assert "L1-01" in rule_ids
        assert "L1-12" in rule_ids

    def test_json_contains_violations(self):
        """JSONに違反情報が含まれる"""
        result = _make_analysis_result()
        parsed = json.loads(json_writer.to_json(result))

        evaluations = parsed["sheets"][0]["評価対象エリア"][0]["評価内容"]
        l1_12 = next(e for e in evaluations if e["ルールID"] == "L1-12")

        assert len(l1_12["違反"]) == 1
        assert l1_12["違反"][0]["セル範囲"] == "A1:C1"

    def test_to_dict_returns_dict(self):
        """to_dictが辞書を返す"""
        result = _make_analysis_result()
        d = json_writer.to_dict(result)

        assert isinstance(d, dict)
        assert set(d["レベル別スコア"].keys()) == {"1", "2", "3"}

    def test_json_skipped_rule_has_flag(self):
        """confidence=0のルールはJSONで判定対象外=trueになる"""
        result = _make_skipped_and_normal_result()
        parsed = json.loads(json_writer.to_json(result))

        rules = {e["ルールID"]: e for e in parsed["sheets"][0]["評価対象エリア"][0]["評価内容"]}
        assert rules["L3-02"]["判定対象外"] is True
        assert rules["L1-01"]["判定対象外"] is False


class TestCsvOutput:
    """CSV出力の統合テスト。"""

    def test_to_csv_string_produces_valid_csv(self):
        """to_csv_stringが有効なCSV文字列を返す"""
        result = _make_analysis_result()
        csv_str = csv_writer.to_csv_string(result)

        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        assert len(rows) >= 2
        assert rows[0] == csv_writer.HEADER

    def test_csv_contains_correct_row_count(self):
        """CSVが正しい行数を含む"""
        result = _make_analysis_result()
        rows = csv_writer.to_rows(result)

        assert len(rows) == 3

    def test_csv_contains_file_name(self):
        """CSVにファイル名が含まれる"""
        result = _make_analysis_result(file_name="集計表.xlsx")
        rows = csv_writer.to_rows(result)

        assert rows[1][0] == "集計表.xlsx"

    def test_csv_pass_fail_in_japanese(self):
        """CSVの合否が日本語で出力される"""
        result = _make_analysis_result()
        rows = csv_writer.to_rows(result)

        status_idx = csv_writer.HEADER.index("合否")
        statuses = {row[status_idx] for row in rows[1:]}
        assert statuses <= {"合格", "不合格"}

    def test_csv_empty_result(self):
        """ルール結果が空の場合もヘッダー行のみ返す"""
        result = AnalysisResult(
            file_meta=FileMeta(name="empty.xlsx", sheet_count=0),
            sheets=[],
        )
        rows = csv_writer.to_rows(result)

        assert len(rows) == 1
        assert rows[0] == csv_writer.HEADER

    def test_csv_skipped_rule_column(self):
        """confidence=0のルールは「判定対象外」列が「○」になる"""
        result = _make_skipped_and_normal_result()
        rows = csv_writer.to_rows(result)

        col = csv_writer.HEADER.index("判定対象外")
        rule_idx = csv_writer.HEADER.index("ルールID")
        by_rule = {r[rule_idx]: r for r in rows[1:]}
        assert by_rule["L3-02"][col] == "○"
        assert by_rule["L1-01"][col] == ""


def _make_bulk_result():
    """テスト用 BulkAnalysisResult を生成する。"""
    from harunobu.rules.bulk_base import BulkAnalysisResult

    r1 = _make_analysis_result(file_name="data_R3.xlsx")
    r2 = _make_analysis_result(file_name="data_R4.xlsx")
    bulk_check = CheckResult(
        rule_id="L3-07",
        passed=False,
        confidence=0.8,
        message="複数ファイル間のフォーマット不整合: 1件検出",
        violations=[
            Violation(
                sheet="(bulk)",
                cell_range="",
                description="列数が変動しています",
                severity="warning",
            )
        ],
    )
    return BulkAnalysisResult(files=[r1, r2], bulk_checks={"L3-07": bulk_check})


class TestBulkJsonOutput:
    """bulk JSON 出力の統合テスト。"""

    def test_to_bulk_json_includes_total_and_checks(self):
        """bulk JSON に複数ファイル総合スコアとファイル横断チェックが含まれる。"""
        bulk = _make_bulk_result()
        parsed = json.loads(json_writer.to_bulk_json(bulk))

        assert "複数ファイル総合スコア" in parsed
        assert parsed["ファイル数"] == 2
        assert "L3-07" in parsed["ファイル横断チェック"]
        assert parsed["ファイル横断チェック"]["L3-07"]["合否"] is False

    def test_to_bulk_json_includes_per_file_results(self):
        """bulk JSON に各ファイルの結果が含まれる。"""
        bulk = _make_bulk_result()
        parsed = json.loads(json_writer.to_bulk_json(bulk))

        file_names = [r["inputファイル名"] for r in parsed["ファイル別結果"]]
        assert file_names == ["data_R3.xlsx", "data_R4.xlsx"]


class TestBulkCsvOutput:
    """bulk CSV 出力の統合テスト。"""

    def test_to_bulk_csv_includes_bulk_row(self):
        """bulk CSV に ファイル名=(bulk) の行で横断チェック結果が含まれる。"""
        bulk = _make_bulk_result()
        rows = csv_writer.to_bulk_rows(bulk)

        # ヘッダー + 各ファイル 2行 × 2ファイル + bulk 1行 = 6 行
        assert rows[0] == csv_writer.HEADER
        bulk_rows = [r for r in rows[1:] if r[0] == "(bulk)"]
        assert len(bulk_rows) == 1
        rule_idx = csv_writer.HEADER.index("ルールID")
        status_idx = csv_writer.HEADER.index("合否")
        assert bulk_rows[0][rule_idx] == "L3-07"
        assert bulk_rows[0][status_idx] == "不合格"

    def test_to_bulk_csv_string_is_valid(self):
        """to_bulk_csv_string が有効な CSV を返す。"""
        bulk = _make_bulk_result()
        csv_str = csv_writer.to_bulk_csv_string(bulk)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[0] == csv_writer.HEADER
        assert any(r[0] == "(bulk)" for r in rows[1:])
