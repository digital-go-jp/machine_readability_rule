"""L1-09: 空白とゼロの区別チェック"""

from __future__ import annotations

from harunobu.core.ai_semantic_checker import AISemanticChecker
from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class BlankVsZeroRule(RuleBase):
    """空白セルとゼロ値の区別が適切であることを確認する。"""

    rule_id = "L1-09"
    rule_name = "空白とゼロが明確に区別されているか"
    level = 1
    target = TargetFormat.COMMON
    description = "数値列における空白セルとゼロ値の区別が適切であることを確認します。"

    severity = Severity.MINOR
    NUMERIC_COLUMN_THRESHOLD = 0.7
    MIN_DATA_ROWS = 3

    def _scan_column(self, context: TableContext, col: int) -> tuple[bool, int, int, list]:
        """数値列判定・空白数・ゼロ数・サンプル値を1パスで収集する。"""
        sheet = context.sheet
        region = context.table_region.range
        layout = context.table_region.layout
        body_start = layout.body_start_row

        numeric_count = 0
        total_count = 0
        blank_count = 0
        zero_count = 0
        sample_values: list = []

        for r in range(body_start, region.end_row + 1):
            val = sheet.get_cell_value(r, col)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                blank_count += 1
                continue
            total_count += 1
            is_zero = False
            if isinstance(val, (int, float)):
                numeric_count += 1
                is_zero = val == 0
            else:
                try:
                    is_zero = float(str(val).replace(",", "")) == 0
                    numeric_count += 1
                except (ValueError, TypeError):
                    pass
            if is_zero:
                zero_count += 1
            if len(sample_values) < 10:
                sample_values.append(val)

        is_numeric = total_count > 0 and numeric_count / total_count >= self.NUMERIC_COLUMN_THRESHOLD
        return is_numeric, blank_count, zero_count, sample_values

    def check(self, context: TableContext) -> CheckResult:
        """数値列で空白セルとゼロ値が適切に区別されているかを検査する。"""
        checker = AISemanticChecker.get_instance()
        if not checker.is_available():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0,
                violations=[],
                message="このルールはAIモードON時のみ判定します",
            )

        sheet = context.sheet
        region = context.table_region.range
        layout = context.table_region.layout

        body_start = layout.body_start_row
        body_end = region.end_row

        if body_end - body_start + 1 < self.MIN_DATA_ROWS:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0,
                violations=[],
                message="データ行数が少ないため判定をスキップしました",
            )

        ambiguous: list[tuple[int, str, int, int, list]] = []

        for c in range(region.start_col, region.end_col + 1):
            is_numeric, blank_count, zero_count, sample_values = self._scan_column(context, c)
            if not is_numeric:
                continue
            if blank_count > 0 and zero_count >= 2:
                header_name = ""
                if layout.header_rows:
                    cell = sheet.get_cell(layout.header_rows[-1], c)
                    if cell and cell.value:
                        header_name = str(cell.value).strip()
                ambiguous.append((c, header_name, blank_count, zero_count, sample_values))

        if not ambiguous:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.8,
                violations=[],
                message="空白・ゼロ混在列はありません",
            )

        items = [(header, samples) for _, header, _, _, samples in ambiguous]
        ai_results = checker.batch_check_zero_unlikely_columns(items)
        if ai_results is None:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0,
                violations=[],
                message="AI判定に失敗したため判定をスキップしました",
            )

        violations: list[Violation] = []
        for (col, header, blank_cnt, zero_cnt, _), ai_result in zip(ambiguous, ai_results):
            if ai_result["zero_unlikely"] and ai_result["confidence"] >= 0.7:
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=f"C{col}",
                        description=(
                            f"列「{header}」（列{col}）に空白（{blank_cnt}件）とゼロ（{zero_cnt}件）が混在しています。"
                            f"「{header}」はゼロが発生しにくい項目のため、"
                            f"空白が「データなし」の誤記である可能性があります（{ai_result['reason']}）。"
                        ),
                        severity="warning",
                    )
                )

        passed = len(violations) == 0
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=0.8,
            violations=violations,
            message=(
                f"ゼロが不自然な列に空白・ゼロ混在: {len(violations)}件検出"
                if violations
                else "空白・ゼロ混在に問題はありません"
            ),
        )
