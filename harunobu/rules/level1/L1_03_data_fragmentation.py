"""L1-03: データ分断チェック（不要な空白行・列による分断）"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class DataFragmentationRule(RuleBase):
    """不要な空白行・列によるデータ分断がないことを確認する。"""

    rule_id = "L1-03"
    rule_name = "データが分断されていないか"
    level = 1
    target = TargetFormat.COMMON
    description = "データ範囲内に不要な空白行・空白列が挿入されていないことを確認します。"

    severity = Severity.CRITICAL

    def _find_empty_rows_in_range(self, context: TableContext) -> list[int]:
        """テーブル領域内の空白行を検出する。"""
        sheet = context.sheet
        region = context.table_region.range
        empty_rows: list[int] = []

        for r in range(region.start_row, region.end_row + 1):
            is_empty = True
            for c in range(region.start_col, region.end_col + 1):
                val = sheet.get_cell_value(r, c)
                if val is not None and str(val).strip() != "":
                    is_empty = False
                    break
            if is_empty:
                empty_rows.append(r)

        return empty_rows

    def _find_empty_cols_in_range(self, context: TableContext) -> list[int]:
        """テーブル領域内の空白列を検出する。

        結合セルの非マスター列（列方向スパンの従属列）はすべてのセルが空に見えるが、
        実際は結合によりマスター列でカバーされているため FP となる。
        そのような列はスキップする。
        """
        sheet = context.sheet
        region = context.table_region.range
        empty_cols: list[int] = []

        for c in range(region.start_col, region.end_col + 1):
            is_empty = True
            all_col_span_non_master = True  # すべてが列スパン非マスターかどうか
            for r in range(region.start_row, region.end_row + 1):
                val = sheet.get_cell_value(r, c)
                if val is not None and str(val).strip() != "":
                    is_empty = False
                    all_col_span_non_master = False
                    break
                # 空セルが列スパン非マスターかチェック
                cell = sheet.get_cell(r, c)
                if not (
                    cell is not None
                    and cell.is_merged
                    and cell.merge_master is not None
                    and cell.merge_master.col != c  # 別の列がマスター（列方向スパン）
                ):
                    all_col_span_non_master = False

            if is_empty and not all_col_span_non_master:
                empty_cols.append(c)

        return empty_cols

    def _row_is_empty_on_sheet(self, sheet, row: int) -> bool:
        """シート全体でその行が完全に空かを判定する。"""
        max_col = getattr(sheet, "max_col", 0) or 0
        if max_col <= 0:
            return True
        for c in range(1, max_col + 1):
            val = sheet.get_cell_value(row, c)
            if val is not None and str(val).strip() != "":
                return False
        return True

    def _find_inter_table_empty_rows(self, context: TableContext) -> list[int]:
        """同一シート上のテーブル間にある空白行を検出する。

        レイアウト推定の gap_threshold によって 2 行以上の空行で分割されたテーブルが
        ある場合、それらの間の空行はテーブル内空白行としては捕捉できない。
        ここで検出して L1-03 違反として報告する。

        重複報告を避けるため、シート内の最初のテーブル（start_row 昇順で先頭）に
        対する呼び出しでのみ列挙する。
        """
        all_tables = context.all_tables
        if not all_tables or len(all_tables) <= 1:
            return []

        sorted_tables = sorted(
            all_tables,
            key=lambda t: (t.range.start_row, t.range.start_col),
        )

        # シート内最初のテーブルでのみ実行（L1-02 と同じ dedupe パターン）
        current = context.table_region
        first = sorted_tables[0]
        if not (current.range.start_row == first.range.start_row and current.range.start_col == first.range.start_col):
            return []

        sheet = context.sheet
        empty_rows: list[int] = []
        for i in range(len(sorted_tables) - 1):
            t1 = sorted_tables[i]
            t2 = sorted_tables[i + 1]
            if t1.range.end_row >= t2.range.start_row:
                continue  # 垂直に分離していない（重なり/同一行範囲）
            for r in range(t1.range.end_row + 1, t2.range.start_row):
                if self._row_is_empty_on_sheet(sheet, r):
                    empty_rows.append(r)

        return empty_rows

    def check(self, context: TableContext) -> CheckResult:
        """不要な空白行・空白列によるデータの分断がないかを検査する。"""
        region = context.table_region.range
        total_rows = region.end_row - region.start_row + 1

        violations: list[Violation] = []
        empty_rows: list[int] = []
        empty_cols: list[int] = []

        # テーブル内の空白行・空白列（小さな領域はデータテーブルではないためスキップ）
        if total_rows > 2:
            empty_rows = self._find_empty_rows_in_range(context)
            empty_cols = self._find_empty_cols_in_range(context)

            for r in empty_rows:
                violations.append(
                    Violation(
                        sheet=context.sheet.name,
                        cell_range=f"行{r}",
                        description=f"データ範囲内の行{r}が空白です。不要な空白行を削除してください。",
                        severity="error",
                    )
                )

            for c in empty_cols:
                violations.append(
                    Violation(
                        sheet=context.sheet.name,
                        cell_range=f"列{c}",
                        description=f"データ範囲内の列{c}が空白です。不要な空白列を削除してください。",
                        severity="error",
                    )
                )

        # テーブル間の空白行（レイアウト推定 gap_threshold で分割されたケース）
        inter_table_empty_rows = self._find_inter_table_empty_rows(context)
        for r in inter_table_empty_rows:
            violations.append(
                Violation(
                    sheet=context.sheet.name,
                    cell_range=f"行{r}",
                    description=(f"テーブル間の行{r}が空白です。空白行で分断せず、1 つの表にまとめてください。"),
                    severity="error",
                )
            )

        if not violations:
            if total_rows <= 2:
                return CheckResult(
                    rule_id=self.rule_id,
                    passed=True,
                    confidence=0.85,
                    message="小さな領域のためチェック対象外です。",
                )
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.85,
                message="データ範囲内に不要な空白行・列はありません。",
            )

        parts: list[str] = []
        if empty_rows:
            parts.append(f"空白行{len(empty_rows)}件")
        if empty_cols:
            parts.append(f"空白列{len(empty_cols)}件")
        if inter_table_empty_rows:
            parts.append(f"テーブル間空白行{len(inter_table_empty_rows)}件")
        message = "データ範囲内に" + "、".join(parts) + "が検出されました。"

        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=0.9,
            violations=violations,
            message=message,
        )
