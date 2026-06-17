"""L1-07: 1セル1データチェック"""

from __future__ import annotations

import re
from typing import Literal

from harunobu.core.models import (
    CellPosition,
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class OneDataPerCellRule(RuleBase):
    """1セルに1つのデータのみが含まれていることを確認する。"""

    rule_id = "L1-07"
    rule_name = "１セル１データとなっているか"
    level = 1
    target = TargetFormat.COMMON
    description = "1つのセルに改行やカンマで区切られた複数のデータが含まれていないことを確認します。"

    severity = Severity.CRITICAL
    _NEWLINE_RE = re.compile(r"\n")
    # 数値の千位区切り以外のカンマ（列挙・区切り）
    _MULTI_ITEM_RE = re.compile(r"(?<!\d),(?!\d)")
    # 単一の千位区切り数値（英数字スタイル）。複数数値のカンマとは切り分ける。
    _THOUSANDS_NUMBER_RE = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$")
    # 全角括弧セグメント（ネストなし想定）を除去
    _FULLWIDTH_PAREN_SEG_RE = re.compile(r"（[^）]*）")
    # NG-02: セル全体が「整数（整数）」のみ
    _TWO_METRICS_PAREN_RE = re.compile(r"^\s*\d+（\d+）\s*$")

    @staticmethod
    def _inferred_type_for_col(
        context: TableContext,
        col: int,
    ) -> Literal["text", "numeric", "date", "mixed", "empty"] | None:
        """layout.columns が空なら None（列型ガードなし）。該当列が無ければ None。"""
        cols = context.table_region.layout.columns
        if not cols:
            return None
        for cs in cols:
            if cs.col_index == col:
                return cs.inferred_type
        return None

    def _has_multiple_data(
        self,
        value: str,
        *,
        col_type: Literal["text", "numeric", "date", "mixed", "empty"] | None,
    ) -> str | None:
        """セル内に複数データが含まれているか判定する。"""
        if self._NEWLINE_RE.search(value):
            lines = [line.strip() for line in value.split("\n") if line.strip()]
            if len(lines) >= 2:
                return "セル内改行による複数データ"

        if self._TWO_METRICS_PAREN_RE.match(value):
            return "全角括弧内に別数値（複数指標の混在）"

        if value.count("、") >= 2:
            return "読点（、）による列挙"

        # 3項目以上の列挙（「A・B・C」）。2項目のみは固有名等の誤検知が出やすいため対象外。
        if value.count("・") >= 2:
            return "中黒（・）による列挙"

        if self._MULTI_ITEM_RE.search(value) and not self._THOUSANDS_NUMBER_RE.fullmatch(value.strip()):
            return "カンマ区切りによる複数データ"

        # 数字同士のカンマ: numeric 列では千位区切りと混同しやすいのでスキップ
        if col_type != "numeric":
            compact = re.sub(r"\s+", "", value)
            compact = self._FULLWIDTH_PAREN_SEG_RE.sub("", compact)
            if "," in compact and not self._THOUSANDS_NUMBER_RE.fullmatch(compact):
                return "カンマ区切りによる複数データ"

        return None

    def check(self, context: TableContext) -> CheckResult:
        """1 つのセルに複数のデータが詰め込まれていないかを検査する。"""
        sheet = context.sheet
        region = context.table_region.range
        violations: list[Violation] = []

        for cell in sheet.iter_cells(region.start_row, region.start_col, region.end_row, region.end_col):
            if cell.value is None:
                continue
            val = str(cell.value)
            if not val.strip():
                continue

            col_type = self._inferred_type_for_col(context, cell.pos.col)
            issue = self._has_multiple_data(val, col_type=col_type)
            if issue:
                pos = CellPosition(row=cell.pos.row, col=cell.pos.col)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=str(pos),
                        description=f"{pos}: {issue}（値: '{val[:50]}'）",
                        severity="warning",
                    )
                )

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.82,
                message="すべてのセルが1セル1データです。",
            )

        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=0.78,
            violations=violations,
            message=f"{len(violations)}件のセルで複数データが検出されました。",
        )
