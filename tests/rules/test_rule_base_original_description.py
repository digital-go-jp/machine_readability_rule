"""RuleBase.original_description のテスト"""

from __future__ import annotations

from harunobu.core.severity import Severity
from harunobu.resources.original_rule_descriptions import load_original_rule_descriptions
from harunobu.rules.base import RuleBase, TargetFormat
from harunobu.rules.registry import registry


class _UnknownRule(RuleBase):
    """テスト用: 同梱リソースに存在しない rule_id を持つルール"""

    rule_id = "L9-99"
    rule_name = "Unknown Rule"
    level = 9
    target = TargetFormat.COMMON
    description = "テスト用の未登録ルール"
    severity = Severity.MAJOR

    def check(self, context):
        raise NotImplementedError


class TestOriginalDescription:
    def test_all_registered_rules_have_original_description(self):
        if not registry.get_all():
            registry.discover()
        for rule in registry.get_all():
            assert rule.original_description, f"{rule.rule_id}: original_description が空です"

    def test_original_description_matches_bundled_resource(self):
        if not registry.get_all():
            registry.discover()
        data = load_original_rule_descriptions()
        for rule in registry.get_all():
            assert rule.original_description == data[rule.rule_id]["description"]

    def test_level_matches_bundled_resource(self):
        """RuleBase.level と同梱リソースの level が整合していることを確認する（docs/ を読まずに検証）。"""
        if not registry.get_all():
            registry.discover()
        data = load_original_rule_descriptions()
        for rule in registry.get_all():
            assert f"Level{rule.level}" == data[rule.rule_id]["level"]

    def test_unknown_rule_id_returns_empty_string(self):
        assert _UnknownRule().original_description == ""
