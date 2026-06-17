"""L2-03: 各列が一意に識別可能な項目名を持っているか"""

from __future__ import annotations

from harunobu.core.models import (
    Cell,
    CellPosition,
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class UniqueHeadersRule(RuleBase):
    """各列の項目名が一意に識別できるかを検査する。

    項目名が重複していると列指定が曖昧になるため、ヘッダ領域から各列の項目名を
    組み立て、重複した項目名を違反として検出する。
    """

    rule_id = "L2-03"
    rule_name = "各列が一意に識別可能な項目名を持っているか"
    level = 2
    target = TargetFormat.COMMON
    description = "各列の項目名が重複していないか確認します。"

    severity = Severity.FATAL

    @staticmethod
    def _cell_range(cell: Cell | None, row: int, col: int) -> str:
        return str(cell.pos) if cell else f"R{row}C{col}"

    def _is_column_empty(self, context: TableContext, col: int) -> bool:
        layout = context.table_region.layout
        sheet = context.sheet
        for row in range(layout.body_start_row, layout.body_end_row + 1):
            cell = sheet.get_cell(row, col)
            if cell is not None and cell.value is not None and str(cell.value).strip() != "":
                return False
        return True

    def _is_merged_header_column(self, context: TableContext, col: int) -> bool:
        """この列のヘッダーセルが結合セルの従属セル（マスターではない）かどうかを判定する。

        reader はマスターセルにも merge_master を自分自身のアドレスで設定するため、
        merge_master が自分自身を指す場合はマスターセルとして扱う。
        fixture では master.merge_master = None なので両方の規約に対応する。
        """
        sheet = context.sheet
        for row in context.table_region.layout.header_rows:
            cell = sheet.get_cell(row, col)
            if cell is None or not cell.is_merged or cell.merge_master is None:
                continue
            master = cell.merge_master
            if master.row != row or master.col != col:
                return True
        return False

    def _find_header_merged_range(self, context: TableContext, col: int) -> tuple[int, int, int, int] | None:
        """指定列のヘッダー領域に重なる結合範囲を 1 つ返す。

        ヘッダー行を走査して、その列に該当する結合のマスターアドレスを特定し、
        sheet.merged_cells から当該結合範囲を取得する。
        無ければ None を返す。
        返り値は (min_row, min_col, max_row, max_col)。
        """
        sheet = context.sheet
        for row in context.table_region.layout.header_rows:
            cell = sheet.get_cell(row, col)
            if cell is None or not cell.is_merged:
                continue
            # master 位置を決定（fixture では master.merge_master=None なので自分自身）
            if cell.merge_master is not None:
                master = cell.merge_master
            else:
                master = CellPosition(row=row, col=col)
            # sheet.merged_cells から master を起点とする結合範囲を探す
            for mr in sheet.merged_cells:
                if mr.start_row == master.row and mr.start_col == master.col:
                    return (mr.start_row, mr.start_col, mr.end_row, mr.end_col)
            # merged_cells に登録されていない場合（fixture によっては master が見つからないことがある）
            # — 同じ master を共有する従属セル群を sheet.cells から推定する。
            min_r = max_r = master.row
            min_c = max_c = master.col
            for (r, c), other in sheet.cells.items():
                if not other.is_merged:
                    continue
                om = other.merge_master
                if om is None:
                    if r == master.row and c == master.col:
                        # master 自身
                        pass
                    else:
                        continue
                elif om.row != master.row or om.col != master.col:
                    continue
                min_r = min(min_r, r)
                max_r = max(max_r, r)
                min_c = min(min_c, c)
                max_c = max(max_c, c)
            return (min_r, min_c, max_r, max_c)
        return None

    @staticmethod
    def _range_to_a1(min_row: int, min_col: int, max_row: int, max_col: int) -> str:
        """(min_row, min_col, max_row, max_col) を A1:B2 形式の文字列に変換する。

        単一セルの場合は "A1" のような単独表記を返す。
        """
        start = str(CellPosition(row=min_row, col=min_col))
        if min_row == max_row and min_col == max_col:
            return start
        end = str(CellPosition(row=max_row, col=max_col))
        return f"{start}:{end}"

    def _build_header_name(self, context: TableContext, col: int) -> str:
        """全ヘッダー行の値を "_" で連結して列の識別名を構築する。"""
        sheet = context.sheet
        parts: list[str] = []
        for row in context.table_region.layout.header_rows:
            cell = sheet.get_cell(row, col)
            if cell is not None and cell.value is not None:
                val = str(cell.value).strip()
                if val and val not in parts:
                    parts.append(val)
        return "_".join(parts)

    def check(self, context: TableContext) -> CheckResult:
        """各列の項目名が一意であり重複していないかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        if not layout.header_rows:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.40,  # ヘッダー行未検出によるスキップ — 判定不能
                violations=[],
                message="ヘッダー行が検出されなかったためスキップ",
            )

        last_header_row = layout.header_rows[-1]

        header_names: dict[str, list[int]] = {}
        # 結合ヘッダー違反は親結合範囲全体を cell_range として報告するため、
        # 同じ結合範囲を持つ複数の従属列で違反が重複しないよう dedupe する。
        seen_merged_ranges: set[str] = set()

        for col in range(table.range.start_col, table.range.end_col + 1):
            if self._is_merged_header_column(context, col):
                # L2 では結合ヘッダーを許容しない。
                # L1-12 ではヘッダー領域のセル結合は許容（info Violation のみ）だが、
                # L2-03 は各列が単独で一意に識別できることを要求するため、
                # 単一行・複数行ヘッダーいずれの場合も結合ヘッダーを違反として扱う。
                # 違反箇所として親結合範囲全体（例: B1:C1）を返す。
                # last_header_row の従属セルだけだとユーザーが横結合の修正対象を
                # 見落とすため、結合範囲全体を A1:B2 形式で報告する。
                merged_range = self._find_header_merged_range(context, col)
                if merged_range is not None:
                    cell_range = self._range_to_a1(*merged_range)
                else:
                    # フォールバック: 単独セル（理論上は通らない想定）
                    cell = sheet.get_cell(last_header_row, col)
                    cell_range = self._cell_range(cell, last_header_row, col)
                if cell_range in seen_merged_ranges:
                    continue
                seen_merged_ranges.add(cell_range)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=cell_range,
                        description="結合ヘッダーの従属セルがあり、列を一意に識別できません",
                        severity="error",
                    )
                )
                continue

            name = self._build_header_name(context, col)

            if not name:
                if not self._is_column_empty(context, col):
                    cell = sheet.get_cell(last_header_row, col)
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=self._cell_range(cell, last_header_row, col),
                            description="項目名が空です",
                            severity="error",
                        )
                    )
                continue

            header_names.setdefault(name, []).append(col)

        for name, cols in header_names.items():
            if len(cols) <= 1:
                continue
            for col in cols:
                cell = sheet.get_cell(last_header_row, col)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=self._cell_range(cell, last_header_row, col),
                        description=f"項目名 '{name}' が重複しています（{len(cols)}列）",
                        severity="error",
                    )
                )

        max(1, table.range.end_col - table.range.start_col + 1)

        return CheckResult(
            rule_id=self.rule_id,
            passed=not violations,
            confidence=0.95,
            violations=violations,
            message=(f"一意でない項目名: {len(violations)}件検出" if violations else "すべての項目名が一意です"),
        )
