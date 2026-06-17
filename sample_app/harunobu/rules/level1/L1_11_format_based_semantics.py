"""L1-11: 書式によるデータ区別チェック"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

try:
    from harunobu.core.ai_visual_analyzer import AIVisualAnalyzer
except ImportError:
    AIVisualAnalyzer = None  # type: ignore[assignment, misc]


class FormatBasedSemanticsRule(RuleBase):
    """書式（色、太字等）のみでデータの意味を区別していないことを確認する。"""

    rule_id = "L1-11"
    rule_name = "【Excel】書式でデータの違いを表現していないか"
    level = 1
    target = TargetFormat.EXCEL
    description = "書式（フォント色、背景色、太字、斜体等）のみでデータの意味を区別していないことを確認します。"

    severity = Severity.CRITICAL
    # デフォルト書式（問題なし）
    _DEFAULT_FONT_COLORS = {None, "000000", "FF000000"}
    _DEFAULT_BG_COLORS = {None, "FFFFFF", "00000000", "FFFFFFFF"}

    def check(self, context: TableContext) -> CheckResult:
        """書式（色・太字等）のみでデータの意味を区別していないかを検査する。"""
        sheet = context.sheet
        region = context.table_region.range

        # CSV/TSVの場合は書式情報がないのでスキップ
        if context.workbook.file_format != "xlsx":
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=1.0,
                message="Excel以外の形式のためチェック対象外です。",
            )

        violations: list[Violation] = []

        # 列ごとに書式のバリエーションを検出
        for c in range(region.start_col, region.end_col + 1):
            font_colors: set[str | None] = set()
            bg_colors: set[str | None] = set()
            bold_count = 0
            italic_count = 0
            total_cells = 0

            body_start = context.table_region.layout.body_start_row
            for r in range(body_start, region.end_row + 1):
                cell = sheet.get_cell(r, c)
                if cell is None:
                    continue
                if cell.value is None or str(cell.value).strip() == "":
                    continue

                total_cells += 1
                font_colors.add(cell.fmt.font_color)
                bg_colors.add(cell.fmt.bg_color)
                if cell.fmt.bold:
                    bold_count += 1
                if cell.fmt.italic:
                    italic_count += 1

            if total_cells < 2:
                continue

            # フォント色のバリエーションが2種以上（デフォルト色を除く）
            non_default_font_colors = font_colors - self._DEFAULT_FONT_COLORS
            if len(non_default_font_colors) >= 1 and len(font_colors) >= 2:
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=f"列{c}",
                        description=f"列{c}でフォント色が複数使用されています（{len(font_colors)}種類）。書式ではなくデータ値で区別してください。",
                        severity="warning",
                    )
                )

            # 背景色のバリエーションが2種以上（デフォルト色を除く）
            non_default_bg_colors = bg_colors - self._DEFAULT_BG_COLORS
            if len(non_default_bg_colors) >= 2:
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=f"列{c}",
                        description=f"列{c}で背景色が複数使用されています（{len(bg_colors)}種類）。書式ではなくデータ値で区別してください。",
                        severity="warning",
                    )
                )

            # 一部のセルだけが太字（ヘッダー以外）
            if 0 < bold_count < total_cells:
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=f"列{c}",
                        description=f"列{c}で一部のセルのみが太字です（{bold_count}/{total_cells}）。書式ではなくデータ値で区別してください。",
                        severity="info",
                    )
                )

            # 一部のセルだけが斜体（ヘッダー以外）
            if 0 < italic_count < total_cells:
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=f"列{c}",
                        description=f"列{c}で一部のセルのみが斜体です（{italic_count}/{total_cells}）。書式ではなくデータ値で区別してください。",
                        severity="info",
                    )
                )

        # ビジュアル分析による補完（見た目から色・書式の意味付けを検出）
        confidence = 0.75
        detected_cells = {v.cell_range for v in violations}
        if AIVisualAnalyzer is not None and context.workbook.file_path:
            try:
                visual = AIVisualAnalyzer.get_instance()
                if visual.is_available():
                    visual_results = visual.check_format_semantics(
                        context.workbook.file_path,
                        context.sheet.name,
                    )
                    for item in visual_results:
                        location = item.get("location", "")
                        if location and location not in detected_cells:
                            meaning = item.get("meaning", "")
                            fmt_type = item.get("format_type", "書式")
                            violations.append(
                                Violation(
                                    sheet=sheet.name,
                                    cell_range=location,
                                    description=(
                                        f"{location}で{fmt_type}による意味付けが検出されました"
                                        f"（推定: {meaning}）。データ値で区別してください。"
                                    ),
                                    severity="warning",
                                )
                            )
                            detected_cells.add(location)
                    confidence = 0.85
            except Exception:
                pass

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=confidence,
                message="書式によるデータ区別は検出されませんでした。",
            )

        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=confidence,
            violations=violations,
            message=f"{len(violations)}件の書式によるデータ区別が検出されました。",
        )
