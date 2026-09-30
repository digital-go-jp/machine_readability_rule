"""L3-09: データが縦持ち形式になっているか

判定で使用する閾値は、`VerticalFormatRule` のクラス属性として明示する。
値は行政データからサンプル抽出した経験的検証に基づく。

- `AI_CONFIDENCE_THRESHOLD = 0.7`: 他ルール (L1-09 等) の AI 確信度閾値と揃える。
- `MAX_TOTAL_COLS = 100`: 列数が 101 以上のテーブルは、時間軸ヘッダーパターンに
  合致しなくても機械可読性が著しく損なわれているため、決定論的に error として扱う。
  100 列以下のグレーゾーンは AI による意味判定に委ねる（AI は補完ではなく
  独立した意味判定として位置付ける）。

時間軸ヘッダーの検出パターン (`_WAREKI_HEADER`) は経験的検証で `R01〜R05` /
`H30` 等の和暦短縮形を含むよう拡張した。これにより `local_public_finance`
配下に多く現れる「年度を R01〜R05 で並べた横持ち表」が、従来の「番号付き
類似列 (info)」ではなく本来の「時間軸横持ち (warning)」として検出される。
"""

from __future__ import annotations

import re

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

# 横持ちを示唆するヘッダーパターン（年や月が列名になっている）
_YEAR_HEADER = re.compile(r"^(19|20)\d{2}\s*(年|年度)?$")
_MONTH_HEADER = re.compile(r"^(\d{1,2})\s*月$")
_PERIOD_HEADER = re.compile(r"^(第?\d+[期回]|(上|下|前|後)半期?|[1-4]Q|Q[1-4]|[上下]期)$")
# 和暦長形 (例: 令和3年, 平成30年度, 令和元年) と短縮形 (例: R01, H30, S64) の両方を受ける
_WAREKI_HEADER = re.compile(r"^(平成|令和|昭和)(\d{1,2}|元)\s*(年|年度)?$|^[RHS]\d{1,2}$")


class VerticalFormatRule(RuleBase):
    """データが縦持ち（ロング）形式になっているかを検査する。

    年・月などが列名となる横持ち（ワイド）形式を検出する。集計・結合処理を
    容易にするため縦持ち形式を推奨し、横持ちと判断される構成を違反として扱う。
    """

    rule_id = "L3-09"
    rule_name = "データが縦持ち形式になっているか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "年・月等が列名になっている場合に多く見られる横持ち（ワイド）形式でないかを確認する。"
        "プログラムによる自動処理やデータ結合を容易にするため、"
        "データは縦持ち（ロング）形式を推奨する。"
    )

    severity = Severity.MAJOR

    # --- 判定閾値（モジュール docstring に根拠を記載）---
    MIN_TOTAL_COLS = 4
    MAX_TOTAL_COLS = 100  # 101 列以上は決定論的に error
    MIN_TIME_AXIS_COLS = 3
    MIN_NUMBERED_GROUP_SIZE = 4
    MIN_HEADERS_FOR_NUMBERED_CHECK = 5
    AI_CONFIDENCE_THRESHOLD = 0.7

    # --- AI 入力パラメータ ---
    AI_SAMPLE_ROWS = 3

    # --- CheckResult.confidence の段階 ---
    CONFIDENCE_DEFAULT = 0.7
    CONFIDENCE_SKIPPED_NO_HEADER = 0.5
    CONFIDENCE_SKIPPED_FEW_COLS = 0.8

    def check(self, context: TableContext) -> CheckResult:
        """データが横持ちでなく縦持ち形式になっているかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        if not layout.header_rows:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=self.CONFIDENCE_SKIPPED_NO_HEADER,
                violations=[],
                message="ヘッダー行が検出されなかったためスキップ",
            )

        header_row = layout.header_rows[-1]
        start_col = table.range.start_col
        end_col = table.range.end_col

        total_cols = end_col - start_col + 1
        if total_cols < self.MIN_TOTAL_COLS:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=self.CONFIDENCE_SKIPPED_FEW_COLS,
                violations=[],
                message="列数が少ないため横持ちの判定対象外",
            )

        # 列数上限を超過するテーブルは決定論的に error とする
        if total_cols > self.MAX_TOTAL_COLS:
            first_cell = sheet.get_cell(header_row, start_col)
            last_cell = sheet.get_cell(header_row, end_col)
            range_str = (
                f"{first_cell.pos if first_cell else f'R{header_row}C{start_col}'}"
                f":{last_cell.pos if last_cell else f'R{header_row}C{end_col}'}"
            )
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=range_str,
                    description=(
                        f"列数が {total_cols} 列と過大です（{self.MAX_TOTAL_COLS} 列超）。"
                        f"横持ち形式の典型例であり、縦持ち形式への変換を強く推奨します"
                    ),
                    severity="error",
                )
            )

        # ヘッダーに年・月・期が並んでいるパターンを検出
        year_cols: list[int] = []
        month_cols: list[int] = []
        period_cols: list[int] = []
        wareki_cols: list[int] = []

        for col in range(start_col, end_col + 1):
            cell = sheet.get_cell(header_row, col)
            if cell is None or cell.value is None:
                continue
            val = str(cell.value).strip()

            if _YEAR_HEADER.match(val):
                year_cols.append(col)
            elif _MONTH_HEADER.match(val):
                month_cols.append(col)
            elif _PERIOD_HEADER.match(val):
                period_cols.append(col)
            elif _WAREKI_HEADER.match(val):
                wareki_cols.append(col)

        is_wide_format = False
        wide_type = ""
        wide_cols: list[int] = []

        if len(year_cols) >= self.MIN_TIME_AXIS_COLS:
            is_wide_format = True
            wide_type = "年"
            wide_cols = year_cols
        elif len(month_cols) >= self.MIN_TIME_AXIS_COLS:
            is_wide_format = True
            wide_type = "月"
            wide_cols = month_cols
        elif len(period_cols) >= self.MIN_TIME_AXIS_COLS:
            is_wide_format = True
            wide_type = "期"
            wide_cols = period_cols
        elif len(wareki_cols) >= self.MIN_TIME_AXIS_COLS:
            is_wide_format = True
            wide_type = "年（和暦）"
            wide_cols = wareki_cols

        if is_wide_format:
            first_cell = sheet.get_cell(header_row, wide_cols[0])
            last_cell = sheet.get_cell(header_row, wide_cols[-1])
            range_str = (
                f"{first_cell.pos if first_cell else f'R{header_row}C{wide_cols[0]}'}"
                f":{last_cell.pos if last_cell else f'R{header_row}C{wide_cols[-1]}'}"
            )

            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=range_str,
                    description=(
                        f"横持ち形式が検出されました: "
                        f"{wide_type}が{len(wide_cols)}列にわたって列名になっています。"
                        f"縦持ち形式への変換を推奨します"
                    ),
                    severity="warning",
                )
            )

        # 類似名称の連続列チェック（数値サフィックスが付いた列名等）
        if not is_wide_format:
            _check_numbered_columns(
                sheet,
                header_row,
                start_col,
                end_col,
                violations,
                min_headers=self.MIN_HEADERS_FOR_NUMBERED_CHECK,
                min_group_size=self.MIN_NUMBERED_GROUP_SIZE,
            )

        # AI による意味判定: 100 列以下のグレーゾーンかつ決定論で未検出のときに限り実行
        if total_cols <= self.MAX_TOTAL_COLS and not violations and AISemanticChecker is not None:
            ai_checker = AISemanticChecker.get_instance()
            if ai_checker.is_available():
                headers: list[str] = []
                for col in range(start_col, end_col + 1):
                    cell = sheet.get_cell(header_row, col)
                    headers.append(str(cell.value).strip() if cell and cell.value else "")

                body_start = layout.body_start_row
                sample_rows: list[list[str]] = []
                for row in range(body_start, min(body_start + self.AI_SAMPLE_ROWS, layout.body_end_row + 1)):
                    row_data: list[str] = []
                    for col in range(start_col, end_col + 1):
                        cell = sheet.get_cell(row, col)
                        row_data.append(str(cell.value).strip() if cell and cell.value is not None else "")
                    sample_rows.append(row_data)

                ai_result = ai_checker.check_wide_format_semantic(headers, sample_rows)

                if ai_result.get("is_wide") and ai_result.get("confidence", 0.0) >= self.AI_CONFIDENCE_THRESHOLD:
                    category_type = ai_result.get("category_type", "")
                    details = ai_result.get("details", "")
                    confidence_val = ai_result.get("confidence", 0.0)

                    first_cell = sheet.get_cell(header_row, start_col)
                    last_cell = sheet.get_cell(header_row, end_col)
                    range_str = (
                        f"{first_cell.pos if first_cell else f'R{header_row}C{start_col}'}"
                        f":{last_cell.pos if last_cell else f'R{header_row}C{end_col}'}"
                    )

                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=range_str,
                            description=(
                                f"横持ち形式が検出されました（AI検出, 確信度: {confidence_val:.0%}）: "
                                f"{category_type}が列名になっています。"
                                f"{details} "
                                f"縦持ち形式への変換を推奨します"
                            ),
                            severity="warning",
                        )
                    )

        passed = len(violations) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=self.CONFIDENCE_DEFAULT,
            violations=violations,
            message=(f"横持ちフォーマット検出: {len(violations)}件" if violations else "データは縦持ち形式です"),
        )


def _check_numbered_columns(
    sheet,
    header_row: int,
    start_col: int,
    end_col: int,
    violations: list[Violation],
    *,
    min_headers: int,
    min_group_size: int,
) -> None:
    """番号付きの類似ヘッダーが連続していないかチェック"""
    headers: list[tuple[int, str]] = []
    for col in range(start_col, end_col + 1):
        cell = sheet.get_cell(header_row, col)
        if cell and cell.value:
            headers.append((col, str(cell.value).strip()))

    if len(headers) < min_headers:
        return

    # ベース名+数字のパターンを検出
    base_name_counts: dict[str, list[int]] = {}
    for col, name in headers:
        m = re.match(r"^(.+?)[\s_\-]?(\d+)$", name)
        if m:
            base = m.group(1).strip()
            # 純粋な数値ヘッダー（コード番号等）はスキップ
            if base.isdigit():
                continue
            if base not in base_name_counts:
                base_name_counts[base] = []
            base_name_counts[base].append(col)

    for base, cols in base_name_counts.items():
        if len(cols) >= min_group_size:
            first_cell = sheet.get_cell(header_row, cols[0])
            last_cell = sheet.get_cell(header_row, cols[-1])
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=(
                        f"{first_cell.pos if first_cell else f'R{header_row}C{cols[0]}'}"
                        f":{last_cell.pos if last_cell else f'R{header_row}C{cols[-1]}'}"
                    ),
                    description=(
                        f"類似名称の列が{len(cols)}列並んでいます"
                        f"（'{base}1', '{base}2', ...）。"
                        f"横持ち形式の可能性があります"
                    ),
                    severity="info",
                )
            )
