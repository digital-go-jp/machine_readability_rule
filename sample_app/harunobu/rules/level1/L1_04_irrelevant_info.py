"""L1-04: データ範囲外の無関係情報チェック"""

from __future__ import annotations

from harunobu.core.models import (
    CellPosition,
    CheckResult,
    OtherCell,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class IrrelevantInfoRule(RuleBase):
    """レイアウト推定でテーブル外に分離されたセル（others）が無いことを確認する。

    ``detect_with_others`` の結果が ``TableContext.sheet_others`` に渡る。タイトル・注釈・
    出典・合計行など region_type にかかわらず、1 セル以上あれば違反とする
    （1 OtherCell につき Violation 1 件）。
    """

    rule_id = "L1-04"
    rule_name = "データ本体と無関係な情報がないか"
    level = 1
    target = TargetFormat.COMMON
    description = "タイトル、注釈など、テーブル外に分離されたセルがないかをチェックします。"

    severity = Severity.MAJOR

    def _violations_from_others(self, sheet_name: str, others: list[OtherCell]) -> list[Violation]:
        """OtherCell ごとに 1 Violation を生成する。"""
        out: list[Violation] = []
        for o in others:
            pos = CellPosition(row=o.row, col=o.col)
            val = o.value
            val_s = "" if val is None else str(val).strip()
            preview = (val_s[:50] + "…") if len(val_s) > 50 else val_s
            out.append(
                Violation(
                    sheet=sheet_name,
                    cell_range=str(pos),
                    description=(
                        f"テーブル外セル（others / {o.region_type}）{pos}: {repr(preview) if preview else '(空)'}"
                    ),
                    severity="warning",
                )
            )
        return out

    def check(self, context: TableContext) -> CheckResult:
        """テーブル外に分離された無関係なセル（others）がないかを検査する。"""
        if not context.sheet_others:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.9,
                message="テーブル外（others）に分離されたセルはありません。",
            )

        violations = self._violations_from_others(context.sheet.name, context.sheet_others)
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=0.9,
            violations=violations,
            message=f"テーブル外（others）に{len(violations)}件のセルがあります。",
        )
