"""出力JSONがスキーマに適合することを検証するテスト"""

from __future__ import annotations

import json
from importlib.resources import files

import jsonschema

from harunobu.core.models import (
    AnalysisResult,
    CellRange,
    CheckResult,
    ColumnHeader,
    ColumnSchema,
    FileMeta,
    MRResult,
    SheetMeta,
    SheetResult,
    TableLayout,
    TableResult,
    Violation,
)
from harunobu.output.json_writer import to_dict


def _load_schema() -> dict:
    resource = files("harunobu.resources").joinpath("analysis-output.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _make_analysis_result(*, with_violations: bool = False) -> AnalysisResult:
    """テスト用の AnalysisResult を生成する。"""
    violations = []
    if with_violations:
        violations = [
            Violation(sheet="Sheet1", cell_range="A1:D1", description="結合セルが検出されました", severity="error"),
        ]

    check = CheckResult(
        rule_id="L1-12",
        passed=not with_violations,
        confidence=0.95,
        violations=violations,
        message="" if not with_violations else "1件のセル結合が検出されました",
    )

    table = TableResult(
        range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
        confidence=0.95,
        mr_result=MRResult(level1={"L1-12": check}),
        column_headers=[
            ColumnHeader(col_index=1, header_rows=[1], label="項目名", is_merged=False),
        ],
        columns=[
            ColumnSchema(col_index=1, inferred_type="text", has_header=True),
        ],
    )

    sheet = SheetResult(
        sheet_meta=SheetMeta(name="Sheet1", used_range="A1:E10", hidden=False),
        tables=[table],
    )

    return AnalysisResult(
        file_meta=FileMeta(name="test.xlsx", size=1024, format="xlsx", sheet_count=1),
        sheets=[sheet],
    )


def test_output_conforms_to_schema() -> None:
    """基本的な出力がスキーマに適合することを確認。"""
    schema = _load_schema()
    result = _make_analysis_result()
    output = to_dict(result)
    jsonschema.validate(instance=output, schema=schema)


def test_output_with_violations_conforms_to_schema() -> None:
    """違反ありの出力がスキーマに適合することを確認。"""
    schema = _load_schema()
    result = _make_analysis_result(with_violations=True)
    output = to_dict(result)
    jsonschema.validate(instance=output, schema=schema)


def test_empty_sheets_conforms_to_schema() -> None:
    """シート情報が空の出力がスキーマに適合することを確認。"""
    schema = _load_schema()
    result = AnalysisResult(
        file_meta=FileMeta(name="empty.csv", size=0, format="csv", sheet_count=0),
        sheets=[],
    )
    output = to_dict(result)
    jsonschema.validate(instance=output, schema=schema)


def test_skipped_rule_conforms_to_schema() -> None:
    """confidence=0（判定対象外）ルールの出力がスキーマに適合することを確認。"""
    schema = _load_schema()
    check = CheckResult(
        rule_id="L3-02",
        passed=True,
        confidence=0,
        violations=[],
        message="このルールは現在判定対象外です",
    )
    table = TableResult(
        range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
        confidence=0.95,
        mr_result=MRResult(level3={"L3-02": check}),
    )
    sheet = SheetResult(
        sheet_meta=SheetMeta(name="Sheet1", used_range="A1:E10", hidden=False),
        tables=[table],
    )
    result = AnalysisResult(
        file_meta=FileMeta(name="test.xlsx", size=1024, format="xlsx", sheet_count=1),
        sheets=[sheet],
    )
    output = to_dict(result)
    jsonschema.validate(instance=output, schema=schema)
