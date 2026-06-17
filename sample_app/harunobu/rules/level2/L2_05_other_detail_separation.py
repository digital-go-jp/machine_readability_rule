"""L2-05: 選択肢列と「その他」の詳細記入が分離されているか"""

from __future__ import annotations

from collections import defaultdict

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

try:
    from harunobu.core.ai_semantic_checker import AISemanticChecker
except ImportError:
    AISemanticChecker = None  # type: ignore[assignment,misc]

_MAX_CARDINALITY = 20
_MIN_BODY_ROWS = 20
_OTHER_MIN_COUNT = 3


class OtherDetailSeparationRule(RuleBase):
    """選択肢列と「その他」の詳細記入が分離されているかを検査する。

    「その他」を選んだ際の自由記述が選択肢と同一セルに混在していると正しく
    集計できないため、選択肢列に詳細記述が混入している列を違反として検出する。
    """

    rule_id = "L2-05"
    rule_name = "選択肢列と「その他」の詳細記入が分離されているか"
    level = 2
    target = TargetFormat.COMMON
    description = "選択肢の回答で「その他」を選んだ際の詳細記述が同一セルに含まれていないか確認します。"

    severity = Severity.MAJOR

    def check(self, context: TableContext) -> CheckResult:
        """選択肢列に「その他」の自由記述が混在していないかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        body_start = layout.body_start_row
        body_end = layout.body_end_row
        start_col = table.range.start_col
        end_col = table.range.end_col

        col_schemas = {cs.col_index: cs for cs in layout.columns}
        ai_checker = AISemanticChecker.get_instance() if AISemanticChecker is not None else None
        ai_available = ai_checker is not None and ai_checker.is_available()

        detected_cell_ranges: set[str] = set()
        # 対象列のデータを AI パスで再利用するために保持する
        qualifying_cols: dict[int, defaultdict[str, list[int]]] = {}

        for col in range(start_col, end_col + 1):
            if col_schemas:
                schema = col_schemas.get(col)
                if schema is not None and schema.inferred_type in ("numeric", "date", "empty"):
                    continue

            col_values: defaultdict[str, list[int]] = defaultdict(list)
            for row in range(body_start, body_end + 1):
                cell = sheet.get_cell(row, col)
                if cell is None or cell.value is None:
                    continue
                val = str(cell.value).strip()
                if val == "":
                    continue
                col_values[val].append(row)

            total_non_empty = sum(len(rows) for rows in col_values.values())
            if total_non_empty < _MIN_BODY_ROWS:
                continue
            if len(col_values) > _MAX_CARDINALITY:
                continue

            qualifying_cols[col] = col_values

            other_values = {val: rows for val, rows in col_values.items() if "その他" in val}

            if len(other_values) >= 2:
                for val, rows in other_values.items():
                    if len(rows) < _OTHER_MIN_COUNT:
                        first_row = rows[0]
                        cell = sheet.get_cell(first_row, col)
                        cell_range_str = str(cell.pos) if cell else f"R{first_row}C{col}"
                        violations.append(
                            Violation(
                                sheet=sheet.name,
                                cell_range=cell_range_str,
                                description=(
                                    f"「その他」の詳細が同一セルに記入されている可能性があります: '{val}'"
                                    f"（「その他」を含む{len(other_values)}種類の値のうち{len(rows)}回のみ出現）"
                                ),
                                severity="warning",
                            )
                        )
                        detected_cell_ranges.add(cell_range_str)

        if not qualifying_cols:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                message="対象となる選択肢列がないため、その他詳細分離チェックをスキップしました。",
            )

        if ai_available:
            header_rows = layout.header_rows
            header_row = header_rows[-1] if header_rows else None

            ai_candidates: list[tuple[str, str, str]] = []
            for col, col_values in qualifying_cols.items():
                header_name = ""
                if header_row is not None:
                    hcell = sheet.get_cell(header_row, col)
                    if hcell and hcell.value is not None:
                        header_name = str(hcell.value).strip()

                for val, rows in col_values.items():
                    if "その他" not in val:
                        continue
                    first_row = rows[0]
                    cell = sheet.get_cell(first_row, col)
                    cell_range_str = str(cell.pos) if cell else f"R{first_row}C{col}"
                    if cell_range_str in detected_cell_ranges:
                        continue
                    ai_candidates.append((val, header_name, cell_range_str))

            if ai_candidates:
                batch_items = [(val, header) for val, header, _ in ai_candidates]
                batch_results = ai_checker.batch_check_other_detail_mixed(batch_items)  # type: ignore[union-attr]
                for i, ai_result in enumerate(batch_results):
                    if ai_result.get("is_mixed") and ai_result.get("confidence", 0) >= 0.7:
                        val, _, cell_range_str = ai_candidates[i]
                        detail_part = ai_result.get("detail_part", "")
                        violations.append(
                            Violation(
                                sheet=sheet.name,
                                cell_range=cell_range_str,
                                description=(
                                    f"「その他」の詳細が同一セルに記入されています（AI検出）: '{val}'"
                                    f"（詳細部分: '{detail_part}'）"
                                ),
                                severity="warning",
                            )
                        )
                        detected_cell_ranges.add(cell_range_str)

        total_data_cells = max(
            1,
            (body_end - body_start + 1) * (end_col - start_col + 1),
        )
        len(violations) / total_data_cells
        passed = len(violations) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=0.85 if ai_available else 0.80,
            violations=violations,
            message=(
                f"「その他」詳細の未分離: {len(violations)}件検出"
                if violations
                else "「その他」と詳細は適切に分離されています"
            ),
        )
