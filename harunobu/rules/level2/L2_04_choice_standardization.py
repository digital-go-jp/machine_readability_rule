"""L2-04: 選択肢回答が標準化されているか"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

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

_MAX_CARDINALITY = 20  # 自由記述列スキップ閾値
_MIN_BODY_ROWS = 20  # 分布分析の最小行数
_OUTLIER_MAX_COUNT = 2  # 外れ値の最大出現回数
_OUTLIER_MAX_RATIO = 0.05  # 外れ値の最大出現割合
_SIMILARITY_THRESHOLD = 0.75  # SequenceMatcher 類似度閾値
_ANNOTATION_SUFFIX_RE = re.compile(r"(?<=\S)[\s　]*[※＊＃#（(「【].*$")


class ChoiceStandardizationRule(RuleBase):
    """選択肢回答が統一された表記で標準化されているかを検査する。

    選択肢列の値の分布や表記ゆれ（全角・半角、注釈付きなど）を分析し、
    同じ回答が別カテゴリとして扱われる表記の不統一を違反として検出する。
    """

    rule_id = "L2-04"
    rule_name = "選択肢回答が標準化されているか"
    level = 2
    target = TargetFormat.COMMON
    description = (
        "選択肢の回答が統一された表記で入力されているか（表記揺れがないか）確認します。"
        "数値コードまたは統一文字列で一貫した表記とすること。"
    )

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """選択肢列の回答に表記ゆれがなく標準化されているかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        body_start = layout.body_start_row
        body_end = layout.body_end_row
        start_col = table.range.start_col
        end_col = table.range.end_col

        ai_checker = AISemanticChecker.get_instance() if AISemanticChecker is not None else None
        ai_available = ai_checker is not None and ai_checker.is_available()
        col_schemas = {cs.col_index: cs for cs in layout.columns}
        any_column_analyzed = False

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

            any_column_analyzed = True
            outliers = _find_outliers(col_values, total_non_empty)
            dominant_values = set(col_values.keys()) - outliers

            if not dominant_values:
                continue

            norm_dominant_map = {dom: _normalize(dom) for dom in dominant_values}
            detected_outliers: set[str] = set()
            for outlier in outliers:
                matched, similar_val = _is_variant_of(outlier, norm_dominant_map)
                if not matched:
                    continue
                detected_outliers.add(outlier)
                first_row = col_values[outlier][0]
                cell = sheet.get_cell(first_row, col)
                count = len(col_values[outlier])
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=str(cell.pos) if cell else f"R{first_row}C{col}",
                        description=(f"表記揺れの可能性: '{outlier}' は '{similar_val}' と類似（出現{count}回）"),
                        severity="warning",
                    )
                )

            # 全分布を AI でスキャンし、出現数に関わらず表記揺れを検出する
            if ai_available and len(col_values) >= 2:
                header_name = ""
                if layout.header_rows:
                    header_cell = sheet.get_cell(layout.header_rows[0], col)
                    if header_cell and header_cell.value:
                        header_name = str(header_cell.value)

                ai_groups = ai_checker.check_choice_variants(list(col_values.keys()), header_name)
                for group in ai_groups:
                    if len(group) < 2:
                        continue
                    canonical = max(group, key=lambda v: len(col_values.get(v, [])))
                    group_str = str(sorted(group))
                    for val in group:
                        if val == canonical or val in detected_outliers or val not in col_values:
                            continue
                        first_row = col_values[val][0]
                        cell = sheet.get_cell(first_row, col)
                        violations.append(
                            Violation(
                                sheet=sheet.name,
                                cell_range=str(cell.pos) if cell else f"R{first_row}C{col}",
                                description=(f"表記揺れの可能性（AI検出）: '{val}' （列内に {group_str} が混在）"),
                                severity="warning",
                            )
                        )

        if not any_column_analyzed:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.0,
                message="分布分析に十分なデータがないため、選択肢標準化チェックをスキップしました。",
            )

        max(1, end_col - start_col + 1)
        len({v.cell_range.split(":")[0] for v in violations}) if violations else 0
        passed = len(violations) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=0.85 if ai_available else 0.7,
            violations=violations,
            message=(
                f"選択肢表記の不統一: {len(violations)}件検出" if violations else "選択肢の表記は統一されています"
            ),
        )


def _normalize(val: str) -> str:
    """表記揺れ比較用の正規化: NFKC変換 → 注釈サフィックス除去 → strip"""
    normalized = unicodedata.normalize("NFKC", val)
    normalized = _ANNOTATION_SUFFIX_RE.sub("", normalized)
    return normalized.strip()


def _find_outliers(col_values: dict[str, list[int]], total_rows: int) -> set[str]:
    """出現回数が少ない外れ値候補を返す"""
    return {
        val
        for val, rows in col_values.items()
        if len(rows) <= _OUTLIER_MAX_COUNT and len(rows) / total_rows <= _OUTLIER_MAX_RATIO
    }


def _is_variant_of(candidate: str, norm_dominant_map: dict[str, str]) -> tuple[bool, str]:
    """候補値が支配的な値のいずれかと類似しているか判定する。"""
    norm_candidate = _normalize(candidate)
    for dominant, norm_dominant in norm_dominant_map.items():
        if norm_candidate == norm_dominant:
            return True, dominant
        if min(len(norm_candidate), len(norm_dominant)) >= 2:
            ratio = SequenceMatcher(None, norm_candidate, norm_dominant).ratio()
            if ratio >= _SIMILARITY_THRESHOLD:
                return True, dominant
    return False, ""
