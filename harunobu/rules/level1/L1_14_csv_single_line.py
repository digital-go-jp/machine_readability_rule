"""L1-14: CSV内のデータ内改行チェック"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class CsvSingleLineRule(RuleBase):
    """CSV内にデータ内改行がないことを確認する。"""

    rule_id = "L1-14"
    rule_name = "【CSV】１行１データで表現されているか"
    level = 1
    target = TargetFormat.CSV
    description = "CSVファイル内のセルにデータ内改行が含まれていないことを確認します。"

    severity = Severity.FATAL

    def check(self, context: TableContext) -> CheckResult:
        """CSV のセル内にデータ内改行が含まれていないかを検査する。"""
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

        diagnostics = getattr(sheet, "csv_diagnostics", None)
        if diagnostics is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                message="CSV raw診断情報がないため、データ内改行チェックをスキップしました。",
            )

        issue_types = {"multiline_record", "unclosed_quote"}
        total_issue_count = sum(diagnostics.issue_counts.get(issue_type, 0) for issue_type in issue_types)
        for sample in diagnostics.issue_samples:
            if sample.issue_type not in issue_types:
                continue
            if not (region.start_row <= sample.logical_row <= region.end_row):
                continue

            physical = (
                f"物理行{sample.physical_start_line}-{sample.physical_end_line}"
                if sample.physical_end_line != sample.physical_start_line
                else f"物理行{sample.physical_start_line}"
            )
            description = f"論理行{sample.logical_row}が{physical}にまたがっています。"
            if sample.issue_type == "unclosed_quote":
                description += " クォートが閉じられていない可能性があります。"
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=f"{sample.logical_row}:{sample.logical_row}",
                    description=description,
                    severity="error",
                )
            )

        if not violations and total_issue_count == 0:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=diagnostics.confidence,
                message="データ内改行は検出されませんでした。",
            )

        message = f"{total_issue_count}件のデータ内改行またはクォート不整合が検出されました。"
        if diagnostics.truncated:
            message = (
                f"少なくとも{total_issue_count}件のデータ内改行またはクォート不整合が検出されたため、"
                "診断収集を途中で打ち切りました。"
            )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=diagnostics.confidence,
            violations=violations,
            message=message,
        )
