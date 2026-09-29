"""L3-03: 特殊記号の定義を明記しているか"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class SpecialSymbolsRule(RuleBase):
    """特殊記号の定義が明記されているかを検査する。

    秘匿記号や欠損値記号などの特殊記号には意味と処理方法の明記が必要だが、
    現状は判定対象外として常に pass を返す。
    """

    rule_id = "L3-03"
    rule_name = "数値データの同一列内に特殊記号（秘匿等）を使用する場合は、その定義を明記しているか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "統計データで使用される秘匿記号や欠損値記号等の特殊記号については、"
        "その意味と処理方法を凡例やメタデータとして明記すること。（判定対象外）"
    )

    severity = Severity.MAJOR

    def check(self, context: TableContext) -> CheckResult:
        """特殊記号の定義明記を検査する（現状は判定対象外）。"""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            confidence=0,
            violations=[],
            message="このルールは現在判定対象外です",
        )
