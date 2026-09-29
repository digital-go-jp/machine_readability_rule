"""L3-08: データの定義や更新履歴が記載されているか"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class MetadataRule(RuleBase):
    """データの定義や更新履歴などのメタデータが記載されているかを検査する。

    項目定義・算出方法・更新履歴などのメタデータ記載が必要だが、
    現状は判定対象外として常に pass を返す。
    """

    rule_id = "L3-08"
    rule_name = "データの定義や更新履歴が記載されているか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "データの正しい解釈と利用のために、項目定義、算出方法、更新履歴等のメタデータを記載すること。（判定対象外）"
    )

    severity = Severity.MAJOR

    def check(self, context: TableContext) -> CheckResult:
        """メタデータの記載を検査する（現状は判定対象外）。"""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            confidence=0,
            violations=[],
            message="このルールは現在判定対象外です",
        )
