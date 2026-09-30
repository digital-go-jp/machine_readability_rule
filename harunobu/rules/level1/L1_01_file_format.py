"""L1-01: ファイル形式チェック（xlsx/csv/tsv以外を拒否）"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class FileFormatRule(RuleBase):
    """ファイル形式がxlsx/csv/tsvであることを確認する。.xlsは拒否。

    拡張子偽装の検出は reader レイヤー (validate_file_mime) で行うため、
    ルール側は拡張子ベースの判定のみ行う。
    """

    rule_id = "L1-01"
    rule_name = "ファイル形式は機械が直接読み取れるExcelやCSV等となっているか"
    level = 1
    target = TargetFormat.COMMON
    description = "ファイル形式がxlsx/csv/tsvであることを確認します。"

    severity = Severity.FATAL
    ALLOWED_FORMATS = {"xlsx", "csv", "tsv"}

    def check(self, context: TableContext) -> CheckResult:
        """ファイル形式が xlsx/csv/tsv のいずれかであるかを検査する。"""
        file_format = context.workbook.file_format
        file_name = context.workbook.file_name

        if file_format in self.ALLOWED_FORMATS:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,  # 決定論的: ファイル拡張子の完全一致判定
                message=f"ファイル形式 '{file_format}' は許可された形式です。",
            )

        # .xls等の非推奨形式
        violations = [
            Violation(
                sheet=context.sheet.name,
                cell_range="ファイル全体",
                description=(
                    f"ファイル '{file_name}' の形式 '{file_format}' は"
                    "許可されていません。xlsx/csv/tsvのいずれかに変換してください。"
                ),
                severity="error",
            )
        ]
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=1.0,
            violations=violations,
            message=f"ファイル形式 '{file_format}' は非推奨です。",
        )
