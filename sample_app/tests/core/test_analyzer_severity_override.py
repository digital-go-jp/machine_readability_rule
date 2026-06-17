"""Analyzer の severity 注入優先順位テスト

ルールが ``check()`` 内で ``CheckResult.severity`` を明示的に設定したら
``MRChecker`` はそれを尊重し、クラス属性で上書きしないことを検証する。
これにより L1-12 のように条件次第で severity を変えるルールが書ける。
"""

from __future__ import annotations

import pytest

from harunobu.core.analyzer import MRChecker
from harunobu.core.models import CheckResult, Config
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat
from harunobu.rules.registry import RuleRegistry


class _DynamicSeverityRule(RuleBase):
    """check() 内で severity を動的に設定するテスト用ルール。"""

    rule_id = "TEST_DYN"
    rule_name = "動的 severity テスト"
    level = 1
    target = TargetFormat.COMMON
    description = "動的 severity を返すテスト用ルール"
    severity = Severity.MAJOR  # クラス属性のデフォルト

    def __init__(self, dynamic_severity: Severity | None) -> None:
        super().__init__()
        self._dynamic = dynamic_severity

    def check(self, context):
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            severity=self._dynamic,
            confidence=1.0,
            message="dynamic test",
        )


def _run_single_rule(rule: RuleBase, ctx) -> CheckResult:
    registry = RuleRegistry()
    registry._rules[rule.rule_id] = rule
    checker = MRChecker(rule_registry=registry)
    config = Config(mr_levels={1}, custom_rules=[rule.rule_id])
    result = checker.check_all(ctx, config)
    assert rule.rule_id in result.level1, "ルールが実行されていない"
    return result.level1[rule.rule_id]


@pytest.fixture
def ctx(create_context):
    """テーブル内容のあるシンプルな TableContext。"""
    return create_context({"Sheet1": [["A", "B"], [1, 2]]})


class TestSeverityOverride:
    def test_rule_explicit_severity_is_respected(self, ctx):
        """ルールが check() で severity=FATAL を返したらクラス属性で上書きされない。

        クラス属性は MAJOR だが、check() 内で FATAL を設定したケース。
        analyzer は None 以外を尊重するため、FATAL のまま残る。
        """
        rule = _DynamicSeverityRule(dynamic_severity=Severity.FATAL)
        cr = _run_single_rule(rule, ctx)
        assert cr.severity == Severity.FATAL

    def test_unset_severity_is_filled_from_class_attribute(self, ctx):
        """severity=None で返すと、クラス属性 (MAJOR) で注入される。"""
        rule = _DynamicSeverityRule(dynamic_severity=None)
        cr = _run_single_rule(rule, ctx)
        assert cr.severity == Severity.MAJOR

    def test_rule_can_lower_severity_below_class_attribute(self, ctx):
        """クラス属性 (FATAL) より弱い severity を返した場合もそれを尊重する。

        L1-12 のヘッダー結合（ボディなら FATAL だがヘッダーは MAJOR にしたい等）の
        動的 severity 変更パターンに相当する。
        """

        class _StrictRule(_DynamicSeverityRule):
            severity = Severity.FATAL

        rule = _StrictRule(dynamic_severity=Severity.MAJOR)
        cr = _run_single_rule(rule, ctx)
        assert cr.severity == Severity.MAJOR
