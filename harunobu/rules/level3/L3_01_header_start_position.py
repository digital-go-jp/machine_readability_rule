"""L3-01: 項目名行から始まり、次行からデータ入力がされているか

機械可読性の観点から、ファイル先頭行（またはシート 1 行目）が項目名行となり、
直後の行からデータが始まる構成であることを要求する。

L3 はテーブル構造の最も厳密なレベルであるため、「ファイル先頭行が項目名行」を
厳格に要求する。すなわち、先頭の空行も違反扱いとし、``table_start_row > 1`` で
あれば（その上の行に内容があってもなくても）違反として検出する。
重大度は ``Severity.FATAL``。

違反種別ごとに重大度を切り替える:

- テーブル開始行が 2 行目以降（``table_start_row > 1``）。
  先頭の空行のみのケースも含めて違反扱い:
  ``Severity.FATAL``（強制 0 点トリガー）。``Violation.severity="error"``。
- ヘッダー行とデータ開始行の間に空行が挟まる:
  ``Severity.FATAL``。``Violation.severity="error"``。
- ヘッダーが 3 行以上にまたがる（多段ヘッダー）:
  ``Severity.MAJOR``（部分減点、強制 0 点ではない）。
  ``Violation.severity="info"``。2 行ヘッダーは階層ヘッダーの慣行として許容。

FATAL 違反と MAJOR 違反が共存する場合は ``CheckResult.severity = FATAL`` を採用する
（``L1-12`` と同じ条件分岐パターン）。
"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

MULTI_HEADER_ROW_THRESHOLD = 3
"""ヘッダー行数がこの値以上で多段ヘッダーと判定する（2 行ヘッダーは許容）。"""


class HeaderStartPositionRule(RuleBase):
    """項目名行から始まり次行からデータが入力されているかを検査する。

    自動読み込みを容易にするため、先頭行が項目名行で次行からデータが始まる構成かを確認し、
    タイトル行やメタ情報が先頭に含まれる場合を違反として検出する。
    """

    rule_id = "L3-01"
    rule_name = "項目名行から始まり、次行からデータ入力がされているか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "ファイルの先頭行（またはシートの1行目）が項目名行（ヘッダー）となり、"
        "次行からデータが始まる構成となっているかを確認します。"
    )

    severity = Severity.FATAL

    def _detect_pre_table_content(self, context: TableContext) -> Violation | None:
        """テーブル開始行が 1 行目でない場合に違反を返す（L3 厳格判定）。

        L3-01 はファイル先頭行を項目名行として要求するため、先頭にタイトル等の
        非データ行があるケースだけでなく、先頭が完全な空行のケースも違反として
        扱う。すなわち ``table_start_row > 1`` 自体を違反条件とする。
        """
        sheet = context.sheet
        table_start_row = context.table_region.range.start_row
        if table_start_row <= 1:
            return None

        return Violation(
            sheet=sheet.name,
            cell_range=f"A1:A{table_start_row - 1}",
            description=(
                f"ファイル先頭行から表が始まっていません"
                f"（先頭から{table_start_row - 1}行の空行・不要行があります）。"
                f"データテーブルは{table_start_row}行目から開始しています"
            ),
            severity="error",
        )

    def _detect_header_body_gap(self, context: TableContext) -> Violation | None:
        """ヘッダー行とデータ開始行の間に空行があれば違反を返す。"""
        layout = context.table_region.layout
        if not layout.header_rows:
            return None

        last_header_row = max(layout.header_rows)
        expected_body_start = last_header_row + 1
        if layout.body_start_row <= expected_body_start:
            return None

        return Violation(
            sheet=context.sheet.name,
            cell_range=f"A{expected_body_start}:A{layout.body_start_row - 1}",
            description=(
                f"ヘッダー行（{last_header_row}行目）とデータ開始行（{layout.body_start_row}行目）の間に空行があります"
            ),
            severity="error",
        )

    def _detect_multi_row_header(self, context: TableContext) -> Violation | None:
        """ヘッダーが 3 行以上にまたがる場合に違反を返す。"""
        layout = context.table_region.layout
        if len(layout.header_rows) < MULTI_HEADER_ROW_THRESHOLD:
            return None

        return Violation(
            sheet=context.sheet.name,
            cell_range=f"A{min(layout.header_rows)}:A{max(layout.header_rows)}",
            description=(
                f"ヘッダーが{len(layout.header_rows)}行にまたがっています。プログラムからの自動読み込みが困難になります"
            ),
            severity="info",
        )

    def check(self, context: TableContext) -> CheckResult:
        """先頭が項目名行で次行からデータが始まる構成かを検査する。"""
        violations: list[Violation] = []
        fatal_count = 0
        major_count = 0

        if v := self._detect_pre_table_content(context):
            violations.append(v)
            fatal_count += 1

        if v := self._detect_header_body_gap(context):
            violations.append(v)
            fatal_count += 1

        if v := self._detect_multi_row_header(context):
            violations.append(v)
            major_count += 1

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.95,
                violations=[],
                message="ヘッダーは適切な位置から開始しています",
            )

        result_severity = Severity.FATAL if fatal_count > 0 else Severity.MAJOR
        parts = []
        if fatal_count > 0:
            parts.append(f"重大違反{fatal_count}件")
        if major_count > 0:
            parts.append(f"多段ヘッダー{major_count}件")
        detail = "（" + "、".join(parts) + "）" if parts else ""

        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            severity=result_severity,
            confidence=0.95,
            violations=violations,
            message=f"ヘッダー開始位置の問題: {len(violations)}件検出{detail}",
        )
