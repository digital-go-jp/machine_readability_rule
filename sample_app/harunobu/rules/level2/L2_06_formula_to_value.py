"""L2-06: 数式を使用している場合は、数値データに修正しているか"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class FormulaToValueRule(RuleBase):
    """数式が値に変換されているかを検査する。

    数式が残っていると参照切れなどで値が変わるリスクがあるため、セル内に数式が
    残存している場合に違反として検出する（Excel のみ対象）。
    """

    rule_id = "L2-06"
    rule_name = "【Excel】数式を使用している場合は、数値データに修正しているか"
    level = 2
    target = TargetFormat.EXCEL
    description = "Excelに数式が残っており、参照先の変更や参照切れにより値が変わるリスクがないか確認します。"

    severity = Severity.MAJOR

    def check(self, context: TableContext) -> CheckResult:
        """セル内に数式が残存していないかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region

        start_row = table.range.start_row
        end_row = table.range.end_row
        start_col = table.range.start_col
        end_col = table.range.end_col

        formula_refs_error = getattr(sheet, "formula_refs_error", None)
        if formula_refs_error:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                violations=[],
                message=f"数式残存を判定できませんでした: {formula_refs_error}",
            )

        seen: set[tuple[int, int]] = set()
        if getattr(sheet, "formula_refs_loaded", False):
            for error_ref in getattr(sheet, "formula_error_refs", []):
                if not _in_range(error_ref.row, error_ref.col, start_row, start_col, end_row, end_col):
                    continue
                coord = (error_ref.row, error_ref.col)
                seen.add(coord)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=error_ref.cell_ref,
                        description=f"参照切れエラーが残存しています: {error_ref.error_text}",
                        severity="error",
                    )
                )

            for formula_ref in getattr(sheet, "formula_refs", []):
                if not _in_range(formula_ref.row, formula_ref.col, start_row, start_col, end_row, end_col):
                    continue
                coord = (formula_ref.row, formula_ref.col)
                if coord in seen:
                    continue
                seen.add(coord)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=formula_ref.cell_ref,
                        description=_formula_description(formula_ref.formula_text, formula_ref.formula_type),
                        severity="error",
                    )
                )
        else:
            for cell in sheet.iter_cells(start_row, start_col, end_row, end_col):
                coord = (cell.pos.row, cell.pos.col)
                if cell.value == "#REF!":
                    seen.add(coord)
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description="参照切れエラーが残存しています: #REF!",
                            severity="error",
                        )
                    )
                    continue

                if cell.formula is not None and cell.formula != "":
                    seen.add(coord)
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description=_formula_description(cell.formula, None),
                            severity="error",
                        )
                    )

        total_cells = max(
            1,
            (end_row - start_row + 1) * (end_col - start_col + 1),
        )
        len(violations) / total_cells
        passed = len(violations) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=1.0,  # 数式の有無は確実に判定可能
            violations=violations,
            message=(f"数式残存: {len(violations)}件検出" if violations else "数式の残存なし"),
        )


def _in_range(row: int, col: int, start_row: int, start_col: int, end_row: int, end_col: int) -> bool:
    return start_row <= row <= end_row and start_col <= col <= end_col


def _formula_description(formula_text: str | None, formula_type: str | None) -> str:
    if formula_text:
        formula_display = formula_text if formula_text.startswith("=") else f"={formula_text}"
        if len(formula_display) > 50:
            formula_display = formula_display[:50] + "..."
        return f"数式が残存しています: {formula_display}"
    if formula_type:
        return f"数式セルが残存しています（{formula_type} formula）"
    return "数式セルが残存しています"
