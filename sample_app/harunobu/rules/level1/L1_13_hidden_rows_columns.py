"""L1-13: 非表示行・列チェック"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class HiddenRowsColumnsRule(RuleBase):
    """非表示の行・列が存在しないことを確認する。"""

    rule_id = "L1-13"
    rule_name = "【Excel】不要な行や列が非表示のまま残されていないか"
    level = 1
    target = TargetFormat.EXCEL
    description = "非表示の行・列が存在しないことを確認します。"

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """非表示の行・列が存在しないかを検査する。"""
        sheet = context.sheet

        # CSV/TSVの場合は非表示行列がないのでスキップ
        if context.workbook.file_format != "xlsx":
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="Excel以外の形式のためチェック対象外です。",
            )

        violations: list[Violation] = []

        # L1-13はtable_region単位ではなく、シート使用範囲内の非表示行・列を違反として扱う。
        hidden_rows_in_used_range = [r for r in sheet.hidden_rows if 1 <= r <= sheet.max_row]
        if hidden_rows_in_used_range:
            groups = self._group_consecutive(hidden_rows_in_used_range)
            for group in groups:
                if len(group) == 1:
                    cell_range = f"行{group[0]}"
                    desc = f"シート使用範囲内の行{group[0]}が非表示です。"
                else:
                    cell_range = f"行{group[0]}-{group[-1]}"
                    desc = f"シート使用範囲内の行{group[0]}〜{group[-1]}が非表示です（{len(group)}行）。"
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=cell_range,
                        description=desc,
                        severity="error",
                    )
                )

        hidden_cols_in_used_range = [c for c in sheet.hidden_cols if 1 <= c <= sheet.max_col]
        if hidden_cols_in_used_range:
            groups = self._group_consecutive(hidden_cols_in_used_range)
            for group in groups:
                if len(group) == 1:
                    cell_range = f"列{group[0]}"
                    desc = f"シート使用範囲内の列{group[0]}が非表示です。"
                else:
                    cell_range = f"列{group[0]}-{group[-1]}"
                    desc = f"シート使用範囲内の列{group[0]}〜{group[-1]}が非表示です（{len(group)}列）。"
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=cell_range,
                        description=desc,
                        severity="error",
                    )
                )

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="シート使用範囲内に非表示の行・列はありません。",
            )

        len(hidden_rows_in_used_range) + len(hidden_cols_in_used_range)
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=1.0,
            violations=violations,
            message=(
                f"シート使用範囲内の非表示行{len(hidden_rows_in_used_range)}件、"
                f"非表示列{len(hidden_cols_in_used_range)}件が検出されました。"
            ),
        )

    @staticmethod
    def _group_consecutive(nums: list[int]) -> list[list[int]]:
        """連続する数値をグループ化する。"""
        if not nums:
            return []

        sorted_nums = sorted(nums)
        groups: list[list[int]] = [[sorted_nums[0]]]

        for n in sorted_nums[1:]:
            if n == groups[-1][-1] + 1:
                groups[-1].append(n)
            else:
                groups.append([n])

        return groups
