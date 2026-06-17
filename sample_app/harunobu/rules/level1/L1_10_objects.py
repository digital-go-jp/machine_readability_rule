"""L1-10: オブジェクト（画像・図形）の存在チェック"""

from __future__ import annotations

from harunobu.core.models import (
    CellPosition,
    CellRange,
    CheckResult,
    ObjectRef,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


def _object_ref_intersects_table_range(ref: ObjectRef, table: CellRange) -> bool:
    """ObjectRef のアンカーが表範囲内のとき True。"""
    return table.start_row <= ref.row <= table.end_row and table.start_col <= ref.col <= table.end_col


class ObjectsRule(RuleBase):
    """検出された表の範囲（CellRange）内にオブジェクトが重ならないことを確認する。

    OOXML drawing*.xml を一次情報として使用する。
    OOXML 読み取りに失敗した場合、または object_refs が未ロードの場合は
    confidence=0.0 で判定不能（abstain）とする。
    """

    rule_id = "L1-10"
    rule_name = "【Excel】オブジェクトを使用していないか"
    level = 1
    target = TargetFormat.EXCEL
    description = (
        "検出された表のセル範囲内に、画像・図形・グラフ等のオブジェクトが重なっていないことを確認します。"
        "範囲外のオブジェクトは許容します。"
    )

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """表のセル範囲内に画像・図形等のオブジェクトが重なっていないかを検査する。"""
        sheet = context.sheet

        if context.workbook.file_format != "xlsx":
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="Excel以外の形式のためチェック対象外です。",
            )

        object_refs_error = getattr(sheet, "object_refs_error", None)
        if object_refs_error:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                message=f"オブジェクト残存を判定できませんでした: {object_refs_error}",
            )

        if not getattr(sheet, "object_refs_loaded", False):
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                message="オブジェクトメタデータが未ロードのため判定できませんでした。",
            )

        return self._check_from_object_refs(sheet, context.table_region.range, context.table_region.abstain)

    def _check_from_object_refs(self, sheet, table_range: CellRange, abstain: bool) -> CheckResult:
        """OOXML 由来の ObjectRef を使って判定する。"""
        object_refs: list[ObjectRef] = getattr(sheet, "object_refs", [])
        if not object_refs:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="オブジェクトは検出されませんでした。",
            )

        violations: list[Violation] = []
        for ref in object_refs:
            overlaps = _object_ref_intersects_table_range(ref, table_range)
            if not abstain and not overlaps:
                continue

            cell_label = str(CellPosition(row=ref.row, col=ref.col))
            name_display = ref.name or ref.drawing_part
            if abstain:
                desc = (
                    f"テーブル検出が保留(abstain)のためオブジェクトを確認対象としました: "
                    f"種類={ref.object_type}, 名前={name_display}"
                )
            else:
                desc = (
                    f"表の範囲({table_range})内にオブジェクトが重なります: 種類={ref.object_type}, 名前={name_display}"
                )
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=cell_label,
                    description=desc,
                    severity="error",
                )
            )

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="表の範囲内にオブジェクトは検出されませんでした。",
            )

        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=1.0,
            violations=violations,
            message=f"{len(violations)}件のオブジェクトが表の範囲内に検出されました。",
        )
