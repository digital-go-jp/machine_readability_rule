"""L3-02: 回答のコード表が別添されているか"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class CodeTableRule(RuleBase):
    """回答のコード表が別添されているかを検査する。

    コード値で表現されたデータには意味との対応を定義したコード表の添付が必要だが、
    現状は判定対象外として常に pass を返す。
    """

    rule_id = "L3-02"
    rule_name = "回答のコード表が別添されているか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "コード値で表現されたデータには、コード値と意味の対応を定義した"
        "コード表を別シートまたは別ファイルとして添付すること。（判定対象外）"
    )

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """コード表の別添を検査する（現状は判定対象外）。"""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            confidence=0,
            violations=[],
            message="このルールは現在判定対象外です",
        )
