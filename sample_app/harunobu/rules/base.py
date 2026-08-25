"""ルールプラグイン基底クラス"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from harunobu.core.models import (
    CheckResult,
    TableContext,
)
from harunobu.core.severity import Severity
from harunobu.resources.original_rule_descriptions import load_original_rule_descriptions


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

    @property
    def original_description(self) -> str:
        """デジタル庁 機械可読性チェックリスト原本における当該ルールの説明文。

        ``rule_name``/``description`` とは異なり各ルールのクラス属性としては
        持たせず、``docs/references/machine-readability-rules.json`` を出典とする
        ``app/harunobu/resources/original_rule_descriptions.json`` から rule_id を
        キーに参照する。原本の長文を30ルール分クラス属性へ複製すると更新時の
        同期漏れが起きやすいため、一元管理リソースへのプロパティ参照とした。
        同梱データの更新は ``script/update_original_rule_descriptions.py`` を参照。
        未登録の rule_id の場合は空文字を返す。
        """
        return load_original_rule_descriptions().get(self.rule_id, {}).get("description", "")

    def explain(self) -> str:
        """このルールの背景と対処法を人間向けに説明する。"""
        return self.description
