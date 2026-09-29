"""analyzer.py のエラーハンドリングに関するユニットテスト

ルール実行中の例外が適切に処理されることを検証する:
- クラッシュした check ルールに対して passed=True, confidence=0.0 の CheckResult が返る
- ルールクラスの severity 属性が CheckResult.severity に注入される
- strict モードでは例外が再送出される
"""

from __future__ import annotations

import pytest

from harunobu.core.analyzer import MRChecker
from harunobu.core.models import (
    CheckResult,
    Config,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat
from harunobu.rules.registry import RuleRegistry


class CrashingRule(RuleBase):
    """テスト用: check で常に例外を送出するルール"""

    rule_id = "TEST_CRASH"
    rule_name = "Crashing Rule"
    level = 1
    target = TargetFormat.COMMON
    description = "常にクラッシュするテスト用ルール"
    severity = Severity.CRITICAL

    def check(self, context):
        raise ValueError("テスト用の意図的なエラー")


class PassingRule(RuleBase):
    """テスト用: 常にパスするルール"""

    rule_id = "TEST_PASS"
    rule_name = "Passing Rule"
    level = 1
    target = TargetFormat.COMMON
    description = "常にパスするテスト用ルール"
    severity = Severity.MINOR

    def check(self, context):
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            confidence=1.0,
            message="OK",
        )


@pytest.fixture
def crash_registry():
    """CrashingRule と PassingRule を登録した RuleRegistry を返す。"""
    reg = RuleRegistry()
    crashing = CrashingRule()
    passing = PassingRule()
    reg._rules[crashing.rule_id] = crashing
    reg._rules[passing.rule_id] = passing
    return reg


class TestCheckAllErrorHandling:
    """check_all でルールがクラッシュした場合のテスト"""

    def test_crashing_rule_returns_error_result(self, create_context, crash_registry):
        """クラッシュしたルールは passed=True, confidence=0.0 の結果を返す"""
        ctx = create_context({"Sheet1": [["A", "B"], [1, 2]]})
        config = Config(mr_levels={1})
        checker = MRChecker(rule_registry=crash_registry)

        result = checker.check_all(ctx, config)

        crash_result = result.level1.get("TEST_CRASH")
        assert crash_result is not None
        assert crash_result.passed is True
        assert crash_result.confidence == 0.0
        # severity はルールクラスから注入される
        assert crash_result.severity == Severity.CRITICAL
        assert "ValueError" in crash_result.message
        assert "テスト用の意図的なエラー" in crash_result.message

    def test_crashing_rule_does_not_affect_other_rules(self, create_context, crash_registry):
        """クラッシュしたルールが他のルールの実行を妨げない"""
        ctx = create_context({"Sheet1": [["A", "B"], [1, 2]]})
        config = Config(mr_levels={1})
        checker = MRChecker(rule_registry=crash_registry)

        result = checker.check_all(ctx, config)

        pass_result = result.level1.get("TEST_PASS")
        assert pass_result is not None
        assert pass_result.passed is True
        # severity がルールクラスから注入される
        assert pass_result.severity == Severity.MINOR

    def test_strict_mode_raises_exception(self, create_context, crash_registry):
        """strict=True の場合、ルール例外が再送出される"""
        ctx = create_context({"Sheet1": [["A", "B"], [1, 2]]})
        config = Config(mr_levels={1}, strict=True)
        checker = MRChecker(rule_registry=crash_registry)

        with pytest.raises(ValueError, match="テスト用の意図的なエラー"):
            checker.check_all(ctx, config)

    def test_non_strict_mode_logs_error(self, create_context, crash_registry, caplog):
        """strict=False の場合、エラーがログに記録される"""
        ctx = create_context({"Sheet1": [["A", "B"], [1, 2]]})
        config = Config(mr_levels={1})
        checker = MRChecker(rule_registry=crash_registry)

        import logging

        with caplog.at_level(logging.ERROR):
            checker.check_all(ctx, config)

        assert "TEST_CRASH" in caplog.text
        assert "ValueError" in caplog.text
