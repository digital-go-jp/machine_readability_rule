"""ルールプラグイン基底クラス"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from harunobu.core.models import (
    CheckResult,
    TableContext,
)
from harunobu.core.severity import Severity


class TargetFormat(str, Enum):
    """ルールの適用対象となるファイル形式を表す列挙型。"""

    COMMON = "common"
    EXCEL = "excel"
    CSV = "csv"


class RuleBase(ABC):
    """すべてのルールプラグインの基底クラス。

    ``severity`` はルール失敗時の重大度。Scorer が読み取り、強制 0 点判定に
    用いる。デフォルトは ``Severity.MAJOR``。各ルールはクラス属性で
    オーバーライドする。
    """

    rule_id: str
    rule_name: str
    level: int
    target: TargetFormat
    description: str
    severity: Severity = Severity.MAJOR

    @abstractmethod
    def check(self, context: TableContext) -> CheckResult:
        """ルール適合度をチェックする（決定論的）。

        同一入力に対して常に同一の結果を返すこと（冪等性）。
        """

    def explain(self) -> str:
        """このルールの背景と対処法を人間向けに説明する。"""
        return self.description
