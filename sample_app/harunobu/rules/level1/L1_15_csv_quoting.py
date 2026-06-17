"""L1-15: CSVフィールドのクォーティングチェック"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class CsvQuotingRule(RuleBase):
    """カンマを含むフィールドがダブルクォーテーションで囲まれているか確認する。"""

    rule_id = "L1-15"
    rule_name = '【CSV】文字列にカンマが含まれているフィールドの値はダブルコーテーション（"）で囲んでいるか'
    level = 1
    target = TargetFormat.CSV
    description = (
        "CSVファイルにおいて、カンマやダブルクォーテーションを含むフィールドが"
        "適切にダブルクォーテーションで囲まれているか確認します。"
    )

    severity = Severity.FATAL

    def check(self, context: TableContext) -> CheckResult:
        """カンマ等を含むフィールドが適切にダブルクォートで囲まれているかを検査する。"""
        # Excel形式の場合はチェック対象外
        if context.workbook.file_format not in ("csv", "tsv"):
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="CSV/TSV以外の形式のためチェック対象外です。",
            )

        sheet = context.sheet
        region = context.table_region.range
        violations: list[Violation] = []

        delimiter = "," if context.workbook.file_format == "csv" else "\t"
        diagnostics = getattr(sheet, "csv_diagnostics", None)
        if diagnostics is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                message="CSV raw診断情報がないため、クォーティングチェックをスキップしました。",
            )

        relevant_types = {"unquoted_quote", "unclosed_quote", "field_count_mismatch"}
        total_issue_count = sum(diagnostics.issue_counts.get(issue_type, 0) for issue_type in relevant_types)

        for sample in diagnostics.issue_samples:
            if sample.issue_type not in relevant_types:
                continue
            if not (region.start_row <= sample.logical_row <= region.end_row):
                continue

            if sample.issue_type == "field_count_mismatch":
                description = (
                    f"論理行{sample.logical_row}: 基準列数{sample.expected_field_count}に対して"
                    f"{sample.field_count}列です。未クォートの"
                    f"{'カンマ' if delimiter == ',' else 'タブ'}により列数が崩れている可能性があります。"
                )
                cell_range = f"{sample.logical_row}:{sample.logical_row}"
            elif sample.issue_type == "unclosed_quote":
                description = (
                    f"論理行{sample.logical_row}: クォートが閉じられていません。"
                    "ダブルクォーテーションの対応を確認してください。"
                )
                cell_range = f"{sample.logical_row}:{sample.logical_row}"
            else:
                cell = sample.cell_range or f"{sample.logical_row}:{sample.logical_row}"
                description = (
                    f"{cell}: ダブルクォーテーションを含むフィールドがクォートされていません。"
                    'フィールド全体をダブルクォーテーションで囲み、値中の"は""としてエスケープしてください。'
                )
                cell_range = cell

            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=cell_range,
                    description=description,
                    severity=sample.severity,
                )
            )

        if total_issue_count == 0:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=diagnostics.confidence,
                message="クォーティングに問題はありません。",
            )

        diagnostics.issue_counts.get("unquoted_quote", 0) + diagnostics.issue_counts.get("unclosed_quote", 0)
        diagnostics.issue_counts.get("field_count_mismatch", 0)
        message = f"{total_issue_count}件のクォーティング問題が検出されました。"
        if diagnostics.truncated:
            message = (
                f"少なくとも{total_issue_count}件のクォーティング問題が検出されたため、診断収集を途中で打ち切りました。"
            )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=diagnostics.confidence,
            violations=violations,
            message=message,
        )
