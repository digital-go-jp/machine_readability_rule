"""L3-05: 時間軸の表記が標準化されているか"""

from __future__ import annotations

import re

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

# 和暦パターン
_WAREKI_PATTERN = re.compile(r"(明治|大正|昭和|平成|令和|M|T|S|H|R)\s*(\d{1,2})\s*(年|\.|-|/)")

# 西暦パターン（標準）
_SEIREKI_PATTERN = re.compile(r"(19|20)\d{2}\s*(年|/|-|\.)")

# 年度表記
_NENDO_PATTERN = re.compile(r"(19|20)\d{2}\s*年度")

# e-Stat形式: YYYY年MM月, YYYY/MM/DD 等
_ESTAT_DATE_PATTERN = re.compile(r"^(19|20)\d{2}(年\d{1,2}月(\d{1,2}日)?|/\d{1,2}(/\d{1,2})?|-\d{1,2}(-\d{1,2})?)$")

# ISO 8601 / JIS X 0301（西暦拡張表現）
# 例: 2026-05-13, 2026-05-13T15:30:30, 2026-05-13T15:30:30+09:00, 2026-05-13T15:30:30.123Z
_ISO8601_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")

# JIS X 0301（和暦短縮表現）
# 例: R8.05.13, H15.05.23, R08.05.13T15:30:30
_JIS_X_0301_WAREKI_PATTERN = re.compile(r"^[MTSHR]\d{1,2}\.\d{1,2}\.\d{1,2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")

# 非標準的な日付表記
_NONSTANDARD_DATE_PATTERNS = [
    # "03/04/01" 等の曖昧な日付
    re.compile(r"^\d{2}/\d{1,2}/\d{1,2}$"),
    # "令和3" 年なし
    re.compile(r"^(明治|大正|昭和|平成|令和)\d{1,2}$"),
]

# 時間軸を含むヘッダーのキーワード
_TIME_HEADER_KEYWORDS = re.compile(
    r"(年|月|日|年度|時期|期間|期日|日付|日時|時点|年月|調査時点|対象期間|date|year|month|period)",
    re.IGNORECASE,
)


def _classify_format(val: str) -> str | None:
    """時間軸セル値の表記フォーマットを分類する。

    機械可読な許可フォーマット（ISO 8601 / JIS X 0301 / e-Stat 西暦 / 年度）と、
    違反扱いとなる和暦混入・曖昧表記を判別できる粒度のラベルを返す。

    Args:
        val: セル値の文字列表現。

    Returns:
        分類ラベル。時間軸らしき表記でない場合は ``None``。

    分類ラベル:
        - ``iso8601_datetime``: ISO 8601 日時表記（時刻あり）
        - ``iso8601_date``: ISO 8601 日付のみ表記（YYYY-MM-DD）
        - ``jis_wareki``: JIS X 0301 和暦短縮表記（R8.05.13 等）
        - ``estat_kanji``: e-Stat 漢字区切り（YYYY年M月D日 等）
        - ``estat_slash``: e-Stat スラッシュ区切り（YYYY/M/D 等）
        - ``nendo``: 年度表記（YYYY年度）
        - ``seireki_other``: 西暦先頭だが上記いずれにも該当しない曖昧表記
        - ``wareki``: 和暦表記（違反）
        - ``nonstandard``: 非標準日付表記（違反）
    """
    if _JIS_X_0301_WAREKI_PATTERN.match(val):
        return "jis_wareki"
    if _ISO8601_PATTERN.match(val):
        return "iso8601_datetime" if "T" in val else "iso8601_date"
    if _WAREKI_PATTERN.search(val):
        return "wareki"
    for pattern in _NONSTANDARD_DATE_PATTERNS:
        if pattern.match(val):
            return "nonstandard"
    if _NENDO_PATTERN.match(val):
        return "nendo"
    if _ESTAT_DATE_PATTERN.match(val):
        if "年" in val:
            return "estat_kanji"
        if "/" in val:
            return "estat_slash"
        return "estat_hyphen"
    if _SEIREKI_PATTERN.match(val):
        return "seireki_other"
    return None


# 違反扱いとなる分類ラベル
_VIOLATING_FORMATS = {"wareki", "nonstandard"}


class TimeAxisStandardizationRule(RuleBase):
    """時間軸の表記が標準化されているかを検査する。

    時間軸データが許可フォーマット（e-Stat 準拠の西暦表記、ISO 8601、
    JIS X 0301 西暦拡張・和暦短縮、年度表記）のいずれかで、かつ同一列内で
    一貫しているかを確認する。曖昧な和暦表記（令和3年など）や許可フォーマット
    同士の混在を違反として検出する。
    """

    rule_id = "L3-05"
    rule_name = "時間軸の表記が標準化されているか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "時間軸データは許可フォーマット（e-Stat準拠の西暦表記、ISO 8601、"
        "JIS X 0301 の西暦拡張・和暦短縮、年度表記）のいずれかに該当し、"
        "かつ同一列内で一貫していることを確認します。"
    )

    severity = Severity.MAJOR

    def check(self, context: TableContext) -> CheckResult:
        """時間軸データが許可フォーマットで一貫して記載されているかを検査する。"""
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
        body_start = layout.body_start_row
        body_end = layout.body_end_row

        # 時間軸列の検出
        time_columns: list[int] = []
        for col in range(start_col, end_col + 1):
            cell = sheet.get_cell(header_row, col)
            if cell and cell.value:
                if _TIME_HEADER_KEYWORDS.search(str(cell.value)):
                    time_columns.append(col)

        # ヘッダー自体が時間軸の場合（横持ちの年表記等）
        for col in range(start_col, end_col + 1):
            cell = sheet.get_cell(header_row, col)
            if cell and cell.value:
                val = str(cell.value).strip()
                # 許可フォーマット（ISO 8601 / JIS X 0301）はそのまま許容
                if _ISO8601_PATTERN.match(val) or _JIS_X_0301_WAREKI_PATTERN.match(val):
                    continue
                if _WAREKI_PATTERN.match(val):
                    # JIS X 0301 短縮形でない和暦ヘッダーは違反
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description=f"ヘッダーに和暦表記が使用されています: '{val}'",
                            severity="warning",
                        )
                    )

        # データ行の時間軸列をチェック
        for col in time_columns:
            formats_found: set[str] = set()

            for row in range(body_start, body_end + 1):
                cell = sheet.get_cell(row, col)
                if cell is None or cell.value is None:
                    continue

                val = str(cell.value).strip()
                if not val:
                    continue

                fmt = _classify_format(val)
                if fmt is None:
                    continue

                formats_found.add(fmt)

                if fmt == "wareki":
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description=f"和暦表記が使用されています: '{val}'。西暦に統一してください",
                            severity="error",
                        )
                    )
                elif fmt == "nonstandard":
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description=f"非標準的な日付表記です: '{val}'",
                            severity="warning",
                        )
                    )

            # 許可フォーマット同士でも同一列内での混在は違反扱い
            allowed_formats = formats_found - _VIOLATING_FORMATS
            if len(allowed_formats) > 1:
                header_cell = sheet.get_cell(header_row, col)
                header_name = str(header_cell.value) if header_cell and header_cell.value else f"列{col}"
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=str(header_cell.pos) if header_cell else f"R{header_row}C{col}",
                        description=(
                            f"列 '{header_name}' 内で日付フォーマットが混在しています: {sorted(allowed_formats)}"
                        ),
                        severity="warning",
                    )
                )

        passed = len(violations) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=0.75,
            violations=violations,
            message=(
                f"時間軸表記の問題: {len(violations)}件検出" if violations else "時間軸の表記は標準化されています"
            ),
        )
