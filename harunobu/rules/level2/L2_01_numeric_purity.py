"""L2-01: 数値データは数値属性とし、文字列を含まないこと"""

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

# 違反メッセージ分類用パターン（メッセージにエラー傾向を出すための分類）
_UNIT_PATTERN = re.compile(
    r"([\d,.]+)\s*(人|件|円|千円|百万円|億円|万|千|kg|km|m|g|t|ha|㎡|個|台|回|本|枚|箇所|か所|世帯|戸|社|校|棟|隻|機|両|組|点|冊|食|泊|日|月|年|時間|分|秒|歳|才|度|号|丁目)$"
)
_PERCENT_UNIT_PATTERN = re.compile(r"([\d,.]+)\s*(%|％)$")
_NOTE_PATTERN = re.compile(r"^([\d,.]+)\s*[\(（].*[\)）]$")
_PURE_NUMERIC = re.compile(r"^[\s\-ー−▲△▼]*[\d,]+\.?\d*\s*$")
# 違反チェック専用: ▲△▼ を許容しない厳格な数値文字列パターン
_STRICT_NUMERIC = re.compile(r"^[\s\-ー−]*[\d,]+\.?\d*\s*$")
# ▲△▼ プレフィックス付き数値文字列（日本式負値表記を文字列で入力している場合）
_TRIANGLE_NUMERIC = re.compile(r"^[▲△▼]\s*[\d,]+\.?\d*\s*$")
_PURE_TEXT = re.compile(r"^[^\d]+$")
# 列がパーセント列かどうかを判定するパターン
_PERCENT_VALUE = re.compile(r"^[\s\-ー−▲△▼]*[\d,.]+\s*(%|％)\s*$")


def _is_numeric_value(value) -> bool:
    """セル値が数値的かどうかを判定する。

    LayoutDetector の推定結果とは別に L2-01 ルール独自で判断する。
    LayoutDetector において numeric または mixed と判定された列が対象。
    """
    if isinstance(value, (int, float)):
        return True
    if value is None:
        return False
    val = str(value).strip()
    if not val:
        return False
    if _PURE_NUMERIC.match(val):
        return True
    if _UNIT_PATTERN.match(val):
        return True
    if _PERCENT_UNIT_PATTERN.match(val):
        return True
    if _NOTE_PATTERN.match(val):
        return True
    return False


def _is_percent_column(sheet, col: int, body_start: int, body_end: int) -> bool:
    """列がパーセント列かどうかを判定する。

    非空セルの50%以上がパーセント値（数値+%）であればパーセント列とみなす。
    """
    percent_count = 0
    non_empty = 0
    for row in range(body_start, body_end + 1):
        cell = sheet.get_cell(row, col)
        if cell is None or cell.value is None:
            continue
        val = str(cell.value).strip()
        if not val:
            continue
        non_empty += 1
        if _PERCENT_VALUE.match(val):
            percent_count += 1
    if non_empty == 0:
        return False
    return percent_count / non_empty >= 0.5


class NumericPurityRule(RuleBase):
    """数値データの列に単位や注釈などの文字列が混在していないかを検査する。

    数値主体の列を判定し、単位付き・注釈付きなど数値属性として扱えない値が
    含まれる場合に違反とする。
    """

    rule_id = "L2-01"
    rule_name = "数値データは数値属性とし、文字列を含まないこと"
    level = 2
    target = TargetFormat.COMMON
    description = "数値データのセルに単位や注釈等の文字列が混在していないかを確認します。"

    severity = Severity.FATAL

    def check(self, context: TableContext) -> CheckResult:
        """数値主体の列に文字列が混在していないかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        # ヘッダー行を除いたデータ行を走査
        body_start = layout.body_start_row
        body_end = layout.body_end_row

        # --- 列ごとに数値主体かどうかを判定 ---
        # IslandDetector の ColumnSchema を一次フィルタとして使用する。
        # - "numeric": 80%以上が純粋数値と確認済み → 即採用
        # - "mixed" : 数値と文字列が混在 → _is_numeric_value() で50%超か追加検証
        # - "text" / "date" / "empty": スキップ
        # layout.columns が未設定（空リスト）の場合はすべての列を "mixed" 扱いとして
        # 50%チェックにフォールバックする。
        numeric_cols: set[int] = set()
        percent_cols: set[int] = set()
        col_schemas = {cs.col_index: cs for cs in context.table_region.layout.columns}

        for col in range(table.range.start_col, table.range.end_col + 1):
            if not col_schemas:
                # layout.columns 未設定: 従来ロジックで判定
                _add_to_numeric_cols_if_majority(sheet, col, body_start, body_end, numeric_cols)
            else:
                schema = col_schemas.get(col)
                if schema is None:
                    continue
                if schema.inferred_type == "numeric":
                    # IslandDetector が純粋数値主体と確認済み
                    numeric_cols.add(col)
                elif schema.inferred_type == "mixed":
                    # 単位混在等で "mixed" になった列について追加検証
                    _add_to_numeric_cols_if_majority(sheet, col, body_start, body_end, numeric_cols)
                # "text" / "date" / "empty" はスキップ

            # パーセント列判定（数値列として確定した場合のみ）
            if col in numeric_cols and _is_percent_column(sheet, col, body_start, body_end):
                percent_cols.add(col)

        # --- 数値列のみを対象にチェック ---
        for row in range(body_start, body_end + 1):
            for col in range(table.range.start_col, table.range.end_col + 1):
                # 数値列でなければスキップ
                if col not in numeric_cols:
                    continue

                cell = sheet.get_cell(row, col)
                if cell is None or cell.value is None:
                    continue

                # 既に数値型ならOK
                if isinstance(cell.value, (int, float)):
                    continue

                val = str(cell.value).strip()
                if not val:
                    continue

                # 純粋な数値文字列はOK
                if _STRICT_NUMERIC.match(val):
                    continue

                # 数字を含まない純粋テキストは欠損値マーカーとして許容
                # （「合計なし」「欠損」「-」「N/A」等、統計表で稀に発生する非数値セルが対象）
                if _PURE_TEXT.match(val):
                    continue

                # パーセント列のパーセント値はスキップ
                if col in percent_cols and _PERCENT_VALUE.match(val):
                    continue

                # 除外レイヤーを通過したセルはすべて違反。
                # パターンで分類できる場合はより具体的なメッセージを付与する。
                if _TRIANGLE_NUMERIC.match(val):
                    description = f"数値に文字列が混在しています（負値は数値型で入力してください）: '{val}'"
                    severity: str = "error"
                elif _UNIT_PATTERN.match(val):
                    description = f"数値に単位が混在しています: '{val}'"
                    severity = "error"
                elif _PERCENT_UNIT_PATTERN.match(val):
                    description = f"数値に単位が混在しています: '{val}'"
                    severity = "error"
                elif _NOTE_PATTERN.match(val):
                    description = f"数値に注釈が混在しています: '{val}'"
                    severity = "warning"
                else:
                    description = f"数値列に文字列が混在しています: '{val}'"
                    severity = "error"

                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=str(cell.pos),
                        description=description,
                        severity=severity,
                    )
                )

        # 決定論的チェックで検出済みのセル位置を記録（AI重複除外用）
        detected_cell_ranges: set[str] = {v.cell_range for v in violations}

        # AI セマンティックチェック（利用可能な場合）— バッチで一括処理
        ai_available = False
        if AISemanticChecker is not None:
            ai_checker = AISemanticChecker.get_instance()
            if ai_checker.is_available():
                ai_available = True
                header_rows = layout.header_rows
                header_row = header_rows[-1] if header_rows else None

                # AI に問い合わせるセルを収集
                ai_candidates: list[tuple[str, str, str]] = []  # (val, header_name, cell_range_str)
                for col in numeric_cols:
                    header_name = ""
                    if header_row is not None:
                        hcell = sheet.get_cell(header_row, col)
                        if hcell and hcell.value is not None:
                            header_name = str(hcell.value).strip()

                    for row in range(body_start, body_end + 1):
                        cell = sheet.get_cell(row, col)
                        if cell is None or cell.value is None:
                            continue
                        if isinstance(cell.value, (int, float)):
                            continue

                        val = str(cell.value).strip()
                        if not val:
                            continue

                        cell_range_str = str(cell.pos)
                        if cell_range_str in detected_cell_ranges:
                            continue
                        if _STRICT_NUMERIC.match(val) or _PURE_TEXT.match(val):
                            continue
                        if col in percent_cols and _PERCENT_VALUE.match(val):
                            continue

                        ai_candidates.append((val, header_name, cell_range_str))

                # バッチ API 呼び出し
                if ai_candidates:
                    batch_items = [(val, header) for val, header, _ in ai_candidates]
                    batch_results = ai_checker.batch_check_unit_in_cells(batch_items)
                    for i, ai_result in enumerate(batch_results):
                        if ai_result.get("has_unit") and ai_result.get("confidence", 0) >= 0.7:
                            val, _, cell_range_str = ai_candidates[i]
                            unit_part = ai_result.get("unit_part", "")
                            violations.append(
                                Violation(
                                    sheet=sheet.name,
                                    cell_range=cell_range_str,
                                    description=(
                                        f"数値に単位が混在しています（AI検出）: '{val}'（単位部分: '{unit_part}'）"
                                    ),
                                    severity="warning",
                                )
                            )
                            detected_cell_ranges.add(cell_range_str)

        total_data_cells = max(
            1,
            (body_end - body_start + 1) * (table.range.end_col - table.range.start_col + 1),
        )
        len(violations) / total_data_cells
        passed = len(violations) == 0

        # AI利用時は信頼度を上げる
        confidence = 0.90 if ai_available else 0.85

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=confidence,
            violations=violations,
            message=(f"数値内文字列混在: {len(violations)}件検出" if violations else "数値データに文字列の混在なし"),
        )


def _add_to_numeric_cols_if_majority(sheet, col: int, body_start: int, body_end: int, numeric_cols: set[int]) -> None:
    """非空セルの50%超が数値的と判定したらnumeric_cols に追加する。

    "mixed" 列や layout.columns 未設定時のフォールバックとして使用する。
    _is_numeric_value() は単位付き値（"200円" 等）も数値的とみなし、本ルールのチェック対象とする。
    """
    numeric_count = 0
    non_empty_count = 0
    for row in range(body_start, body_end + 1):
        cell = sheet.get_cell(row, col)
        if cell is None or cell.value is None:
            continue
        val = str(cell.value).strip()
        if not val:
            continue
        non_empty_count += 1
        if _is_numeric_value(cell.value):
            numeric_count += 1
    if non_empty_count > 0 and numeric_count / non_empty_count > 0.5:
        numeric_cols.add(col)
