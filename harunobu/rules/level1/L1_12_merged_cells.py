"""L1-12: セル結合チェック

ヘッダ領域とデータ領域でセル結合の扱いを分離する。

- ヘッダ領域の結合（行政Excelで一般的なマルチヘッダー等）: L1 では許容
  - Violation を severity="info" で記録（出力には残すが pass）
  - CheckResult.severity = Severity.MAJOR（部分減点）
  - L2-03 で改めて一意性が評価される
- データ領域の結合: 機械可読性を著しく損なうため違反
  - Violation を severity="error" で記録
  - CheckResult.severity = Severity.FATAL（強制0点）
"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    MergedRange,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class MergedCellsRule(RuleBase):
    """セル結合の有無を確認する。

    ヘッダ領域の結合は L1 では許容し、L2-03（一意な項目名）で再評価する。
    データ領域の結合は機械可読性への影響が大きいため違反として扱う。
    """

    rule_id = "L1-12"
    rule_name = "【Excel】セルの結合をしていないか"
    level = 1
    target = TargetFormat.EXCEL
    description = (
        "データ領域のセル結合が存在しないことを確認します。"
        "ヘッダー領域の結合はL1では許容しますが、L2-03で一意な項目名の観点から再評価されます。"
    )

    severity = Severity.CRITICAL

    def _is_header_area(self, mc: MergedRange, context: TableContext) -> bool:
        """結合セルがヘッダ領域内にあるかを判定する。"""
        header_rows = context.table_region.layout.header_rows
        if not header_rows:
            return False
        for r in range(mc.start_row, mc.end_row + 1):
            if r not in header_rows:
                return False
        return True

    def check(self, context: TableContext) -> CheckResult:
        """データ領域にセル結合がないかを検査する（ヘッダ領域の結合は許容）。"""
        sheet = context.sheet

        # CSV/TSVの場合はセル結合がないのでスキップ
        if context.workbook.file_format != "xlsx":
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="Excel以外の形式のためチェック対象外です。",
            )

        table_range = context.table_region.range

        merged_cells = [
            mc
            for mc in sheet.merged_cells
            if mc.start_row <= table_range.end_row
            and mc.end_row >= table_range.start_row
            and mc.start_col <= table_range.end_col
            and mc.end_col >= table_range.start_col
        ]
        if not merged_cells:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="セル結合は検出されませんでした。",
            )

        violations: list[Violation] = []
        header_merge_count = 0
        data_merge_count = 0

        for mc in merged_cells:
            is_header = self._is_header_area(mc, context)
            if is_header:
                v_severity = "info"
                area_label = "ヘッダ領域"
                header_merge_count += 1
            else:
                v_severity = "error"
                area_label = "データ領域"
                data_merge_count += 1

            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=str(mc),
                    description=(
                        f"セル結合（{area_label}）: {mc}"
                        f"（{mc.end_row - mc.start_row + 1}行"
                        f" x {mc.end_col - mc.start_col + 1}列）"
                    ),
                    severity=v_severity,
                )
            )

        parts = []
        if header_merge_count > 0:
            parts.append(f"ヘッダ領域{header_merge_count}件")
        if data_merge_count > 0:
            parts.append(f"データ領域{data_merge_count}件")
        detail = "（" + "、".join(parts) + "）" if parts else ""

        if data_merge_count > 0:
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                severity=Severity.FATAL,
                confidence=1.0,
                violations=violations,
                message=f"データ領域にセル結合が{data_merge_count}件検出されました{detail}。",
            )

        # ヘッダー領域の結合のみ → L1 では許容
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            severity=Severity.MAJOR,
            confidence=1.0,
            violations=violations,
            message=(
                f"ヘッダ領域のセル結合が{header_merge_count}件検出されました{detail}。"
                "L1では許容しますが、L2-03で一意な項目名の観点から再評価されます。"
            ),
        )
