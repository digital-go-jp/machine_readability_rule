"""L3-04: データの単位を記載しているか"""

from __future__ import annotations

import re

from harunobu.core.ai_semantic_checker import AISemanticChecker
from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

# ヘッダーに単位が含まれているかのパターン
_UNIT_IN_HEADER = re.compile(
    r"[（(]"
    r"(人|件|円|千円|百万円|億円|万円|%|％|kg|km|m|cm|mm|g|t|ha|㎡|㎢|"
    r"個|台|回|本|枚|箇所|か所|世帯|戸|社|校|棟|隻|機|両|組|点|冊|食|泊|"
    r"日|月|年|時間|分|秒|歳|才|度|kW|kWh|MW|GW|L|mL|dL)"
    r"[）)]"
)

_KNOWN_UNITS = {
    "人",
    "件",
    "円",
    "千円",
    "百万円",
    "億円",
    "万円",
    "%",
    "％",
    "kg",
    "km",
    "m",
    "cm",
    "mm",
    "g",
    "t",
    "ha",
    "㎡",
    "㎢",
    "個",
    "台",
    "回",
    "本",
    "枚",
    "箇所",
    "か所",
    "世帯",
    "戸",
    "社",
    "校",
    "棟",
    "隻",
    "機",
    "両",
    "組",
    "点",
    "冊",
    "食",
    "泊",
    "日",
    "月",
    "年",
    "時間",
    "分",
    "秒",
    "歳",
    "才",
    "度",
    "kW",
    "kWh",
    "MW",
    "GW",
    "L",
    "mL",
    "dL",
}

# 接尾辞で単位が暗示されるもの
_UNIT_SUFFIXES = ("件数", "枚数", "回数", "か所数", "箇所数", "人数", "数")

# 単位不要な日本語キーワード
_UNITLESS_KEYWORDS_JP = (
    "コード",
    "code",
    "番号",
    "No",
    "ID",
    "指数",
    "指標",
    "順位",
    "ランク",
    "フラグ",
    "区分",
)

# 単位不要な英語キーワード（アンダースコア区切りの部分一致で使用）
_UNITLESS_KEYWORDS_EN = frozenset(
    {
        "id",
        "code",
        "key",
        "name",
        "type",
        "flag",
        "status",
        "index",
        "sort",
        "rank",
        "order",
        "level",
        "class",
        "year",
        "month",
        "date",
        "fiscal_year",
        "survey_year",
        "number",
        "count",
        "cnt",
        "num",
        "no",
        "row",
        "col",
        "seq",
        "version",
        "is",
        "has",
        "will",
        "can",
        "use",
    }
)


class DataUnitsRule(RuleBase):
    """数値データ列に単位が記載されているかを検査する。

    数値列の単位が項目名やメタデータに明記されているかを確認し、
    単位が見当たらない数値列を違反として検出する。
    """

    rule_id = "L3-04"
    rule_name = "データの単位を記載しているか"
    level = 3
    target = TargetFormat.COMMON
    description = "すべての数値データ列について、単位が項目名またはメタデータに明記されているか確認します。"

    severity = Severity.MAJOR

    def check(self, context: TableContext) -> CheckResult:
        """数値データ列に単位が記載されているかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        if not layout.header_rows:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.5,
                violations=[],
                message="ヘッダー行が検出されなかったためスキップ",
            )

        header_row = layout.header_rows[-1]
        start_col = table.range.start_col
        end_col = table.range.end_col

        # AI セマンティックチェッカーの準備
        ai_checker = AISemanticChecker.get_instance()
        ai_available = ai_checker.is_available()

        # 決定論的チェックで判定できなかった列を収集（AI バッチ用）
        undetermined_cols: list[tuple[int, str]] = []  # (col, header_text)

        for col in range(start_col, end_col + 1):
            # 列が数値データ列かチェック
            if not _is_numeric_column(sheet, col, layout):
                continue

            # ヘッダーに単位が含まれているかチェック
            cell = sheet.get_cell(header_row, col)
            if cell is None or cell.value is None:
                continue

            header_text = str(cell.value).strip()

            # 1. ヘッダーに単位表記があるか（括弧内に明記されている場合は即パス）
            has_unit = bool(_UNIT_IN_HEADER.search(header_text))

            # 2. ヘッダー名自体が単位を暗示しているか（例: "金額", "人口"）
            if not has_unit:
                has_unit = _header_implies_unit(header_text)

            if has_unit:
                continue

            # 決定論的に判定できなかった列を記録
            undetermined_cols.append((col, header_text))

        # 3. 判定できなかった列を AI に一括問い合わせ
        ai_resolved: set[int] = set()
        if undetermined_cols and ai_available:
            batch_items = [
                (header_text, _get_sample_values(sheet, col, layout)) for col, header_text in undetermined_cols
            ]
            batch_results = ai_checker.batch_infer_units_from_headers(batch_items)
            for i, ai_result in enumerate(batch_results):
                if ai_result.get("has_unit", False):
                    ai_resolved.add(undetermined_cols[i][0])

        for col, header_text in undetermined_cols:
            if col in ai_resolved:
                continue
            cell = sheet.get_cell(header_row, col)
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=str(cell.pos) if cell else f"R{header_row}C{col}",
                    description=(f"数値列 '{header_text}' に単位の記載がありません"),
                    severity="warning",
                )
            )

        passed = len(violations) == 0
        # AI 使用時は confidence を 0.80 に上げる
        confidence = 0.80 if ai_available else 0.65

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=confidence,
            violations=violations,
            message=(
                f"単位未記載の数値列: {len(violations)}件検出"
                if violations
                else "すべての数値列に単位が記載されています"
            ),
        )


def _get_sample_values(sheet, col: int, layout) -> list:
    """数値列の最初の5つのサンプル値を取得する"""
    body_start = layout.body_start_row
    body_end = layout.body_end_row
    sample_values = []
    for row in range(body_start, min(body_end + 1, body_start + 10)):
        cell = sheet.get_cell(row, col)
        if cell and cell.value is not None:
            sample_values.append(cell.value)
            if len(sample_values) >= 5:
                break
    return sample_values


def _is_numeric_column(sheet, col: int, layout) -> bool:
    """列が数値データ列かどうかを判定する"""
    body_start = layout.body_start_row
    body_end = layout.body_end_row

    numeric_count = 0
    total_count = 0

    for row in range(body_start, min(body_end + 1, body_start + 30)):
        cell = sheet.get_cell(row, col)
        if cell is None or cell.value is None:
            continue
        total_count += 1
        if isinstance(cell.value, (int, float)):
            numeric_count += 1
        elif re.fullmatch(r"[\s\-ー−▲△]*[\d,]+\.?\d*\s*", str(cell.value).strip()):
            numeric_count += 1

    if total_count == 0:
        return False
    return numeric_count / total_count >= 0.7


def _header_implies_unit(header: str) -> bool:
    """ヘッダー名から単位が暗示されているか判定する"""
    # ヘッダー名自体が明確な単位を持つもの
    unit_implied_keywords = [
        "金額",
        "価格",
        "費用",
        "コスト",
        "売上",
        "収入",
        "支出",
        "人口",
        "人数",
        "従業員数",
        "利用者数",
        "面積",
        "距離",
        "長さ",
        "高さ",
        "幅",
        "重量",
        "重さ",
        "質量",
        "割合",
        "率",
        "比率",
        "構成比",
        "年齢",
        "年数",
        "温度",
        "気温",
    ]
    if any(kw in header for kw in unit_implied_keywords):
        return True

    # 接尾辞で単位が暗示されるもの（件数、枚数、回数等）
    if any(header.endswith(s) for s in _UNIT_SUFFIXES):
        return True

    # 単位不要なヘッダー（コード、番号、指数、ID、No.等）
    if any(kw in header for kw in _UNITLESS_KEYWORDS_JP):
        return True

    # 数字のみのヘッダー（連番等）は単位不要
    if header.isdigit():
        return True

    # 英語カラム名で単位不要なもの（マスタテーブル等）
    # 完全一致 or アンダースコア区切りの部分一致
    parts = set(header.lower().replace("-", "_").split("_"))
    if parts & _UNITLESS_KEYWORDS_EN:
        return True

    return False
