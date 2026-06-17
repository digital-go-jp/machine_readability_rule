"""L2-02: データ内での項目名等の省略をしていないか"""

from __future__ import annotations

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


class ItemAbbreviationRule(RuleBase):
    """行ヘッダー（表側）に項目値の省略がないかを検査する。

    レイアウト推定が同定した行ヘッダー列（``TableLayout.stub_cols``）に対して、
    省略記号（「〃」「同上」等）や空白による省略が含まれていないかをチェックする。
    行ヘッダーは各行を識別するラベルであり、欠落があると行単位の読み取りが
    不可能になるため、列特性に依存しない単純な原則で判定する。
    """

    rule_id = "L2-02"
    rule_name = "データ内での項目名等の省略をしていないか"
    level = 2
    target = TargetFormat.COMMON
    description = "データ内で項目値が省略（「〃」や「同上」、空白による省略等）されていないか確認します。"

    severity = Severity.FATAL
    # 省略を示す文字列パターン
    _ABBREVIATION_MARKERS = {"〃", "同上", "同左", "同右", "〇", "仝", "ヽ", "々"}

    def check(self, context: TableContext) -> CheckResult:
        """行ヘッダー列に省略記号や空白による省略がないかを検査する。"""
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        stub_cols = layout.stub_cols

        # 行ヘッダーが推定できない場合は採点対象外
        if not stub_cols:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                violations=[],
                message="行ヘッダーが検出できなかったため判定対象外",
            )

        body_start = layout.body_start_row
        body_end = layout.body_end_row

        violations: list[Violation] = []
        # 決定論的チェックで違反が見つかったセルのキー集合（AI 重複除外用）
        detected_cell_keys: set[tuple[int, int]] = set()

        for col in stub_cols:
            prev_value_seen = False
            for row in range(body_start, body_end + 1):
                cell = sheet.get_cell(row, col)
                val = cell.value if cell else None
                val_str = str(val).strip() if val is not None else ""

                # 省略記号の検出
                if val_str in self._ABBREVIATION_MARKERS:
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos) if cell else f"R{row}C{col}",
                            description=f"省略記号が使用されています: '{val_str}'",
                            severity="error",
                        )
                    )
                    detected_cell_keys.add((row, col))
                    # 省略記号の前後で prev_value_seen は維持（空白による省略判定を継続）
                    continue

                # 空白による省略の検出（同列で既に非空白値を観測している場合のみ）
                if val_str == "":
                    if prev_value_seen:
                        violations.append(
                            Violation(
                                sheet=sheet.name,
                                cell_range=str(cell.pos) if cell else f"R{row}C{col}",
                                description="行ヘッダーの値が欠落しています（空白による省略の可能性）",
                                severity="warning",
                            )
                        )
                        detected_cell_keys.add((row, col))
                    # 列先頭の空白は判定対象外（多階層ヘッダー等の可能性）
                    continue

                prev_value_seen = True

        # AI セマンティックチェック（利用可能な場合、行ヘッダー列のみ対象）
        ai_available = False
        if AISemanticChecker is not None:
            ai_checker = AISemanticChecker.get_instance()
            if ai_checker.is_available():
                ai_available = True
                header_row = layout.header_rows[-1] if layout.header_rows else None

                for col in stub_cols:
                    header_name = ""
                    if header_row is not None:
                        hcell = sheet.get_cell(header_row, col)
                        if hcell and hcell.value is not None:
                            header_name = str(hcell.value).strip()

                    column_data: list[tuple[int, int, str]] = []
                    for row in range(body_start, body_end + 1):
                        cell = sheet.get_cell(row, col)
                        val = cell.value if cell else None
                        val_str = str(val).strip() if val is not None else ""
                        if val_str:
                            column_data.append((row, col, val_str))

                    if not column_data:
                        continue

                    ai_results = ai_checker.check_abbreviations(column_data, header_name, sheet.name)
                    for item in ai_results:
                        row = item.get("row")
                        item_col = item.get("col", col)
                        value = item.get("value", "")
                        reason = item.get("reason", "AIによる省略検出")

                        if row is not None and (row, item_col) not in detected_cell_keys:
                            cell = sheet.get_cell(row, item_col)
                            violations.append(
                                Violation(
                                    sheet=sheet.name,
                                    cell_range=str(cell.pos) if cell else f"R{row}C{item_col}",
                                    description=f"省略の可能性があります（AI検出）: '{value}' - {reason}",
                                    severity="warning",
                                )
                            )
                            detected_cell_keys.add((row, item_col))

        passed = len(violations) == 0
        confidence = 0.85 if ai_available else 0.70

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=confidence,
            violations=violations,
            message=(f"項目名省略: {len(violations)}件検出" if violations else "項目名の省略なし"),
        )
