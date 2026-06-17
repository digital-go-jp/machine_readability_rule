"""ルールプラグインの自動発見・登録"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from harunobu.rules.base import RuleBase, TargetFormat


class RuleRegistry:
    """ルールプラグインの自動発見・登録"""

    def __init__(self) -> None:
        self._rules: dict[str, RuleBase] = {}

    def discover(self) -> None:
        """ルールプラグインを自動発見して登録する。

        rules/level*/ 配下の全モジュールをスキャンし、RuleBase のサブクラスを
        rule_id をキーに自動登録する。
        """
        rules_dir = Path(__file__).parent
        for level_dir in sorted(rules_dir.glob("level*")):
            package = f"harunobu.rules.{level_dir.name}"
            for _importer, module_name, _ in pkgutil.iter_modules([str(level_dir)]):
                module = importlib.import_module(f"{package}.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, RuleBase) and attr is not RuleBase:
                        instance = attr()
                        self._rules[instance.rule_id] = instance

    def get(self, rule_id: str) -> RuleBase:
        """rule_id を指定して該当ルールを取得する。"""
        return self._rules[rule_id]

    def get_by_level(self, level: int) -> list[RuleBase]:
        """指定レベルに属するルールの一覧を返す。"""
        return [r for r in self._rules.values() if r.level == level]

    def get_all(self) -> list[RuleBase]:
        """登録されている全ルールの一覧を返す。"""
        return list(self._rules.values())

    def get_by_target(self, target: TargetFormat) -> list[RuleBase]:
        """指定形式に適用されるルール（COMMON を含む）の一覧を返す。"""
        return [r for r in self._rules.values() if r.target in (target, TargetFormat.COMMON)]


registry = RuleRegistry()
