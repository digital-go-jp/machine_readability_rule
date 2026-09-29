"""CheckResult.violation_groups / is_display_truncated のユニットテスト"""

from __future__ import annotations

from harunobu.core.models import (
    VIOLATIONS_DISPLAY_LIMIT,
    CheckResult,
    Violation,
    ViolationGroup,
)


def _violation(
    sheet: str = "Sheet1",
    cell_range: str = "A1",
    description: str = "テスト違反",
    severity: str = "error",
) -> Violation:
    return Violation(sheet=sheet, cell_range=cell_range, description=description, severity=severity)  # type: ignore[arg-type]


def _check_result(violations: list[Violation]) -> CheckResult:
    return CheckResult(
        rule_id="L1-12",
        passed=False,
        confidence=1.0,
        violations=violations,
    )


# ─── is_display_truncated ───


class TestIsDisplayTruncated:
    def test_false_when_at_limit(self) -> None:
        vs = [_violation(cell_range=f"A{i}") for i in range(VIOLATIONS_DISPLAY_LIMIT)]
        cr = _check_result(vs)
        assert cr.is_display_truncated is False

    def test_false_when_below_limit(self) -> None:
        vs = [_violation(cell_range=f"A{i}") for i in range(5)]
        cr = _check_result(vs)
        assert cr.is_display_truncated is False

    def test_true_when_above_limit(self) -> None:
        vs = [_violation(cell_range=f"A{i}") for i in range(VIOLATIONS_DISPLAY_LIMIT + 1)]
        cr = _check_result(vs)
        assert cr.is_display_truncated is True

    def test_false_when_empty(self) -> None:
        cr = _check_result([])
        assert cr.is_display_truncated is False

    def test_violations_unchanged(self) -> None:
        """is_display_truncated は violations を変異させない。"""
        vs = [_violation(cell_range=f"A{i}") for i in range(VIOLATIONS_DISPLAY_LIMIT + 10)]
        cr = _check_result(vs)
        assert len(cr.violations) == VIOLATIONS_DISPLAY_LIMIT + 10


# ─── violation_groups ───


class TestViolationGroups:
    def test_empty_violations_returns_empty_groups(self) -> None:
        cr = _check_result([])
        assert cr.violation_groups == []

    def test_single_group(self) -> None:
        vs = [_violation(sheet="Sheet1", severity="error", cell_range=f"A{i}") for i in range(5)]
        cr = _check_result(vs)
        groups = cr.violation_groups
        assert len(groups) == 1
        assert groups[0].sheet == "Sheet1"
        assert groups[0].severity == "error"
        assert groups[0].count == 5

    def test_groups_by_sheet_and_severity(self) -> None:
        vs = [
            _violation(sheet="Sheet1", severity="error", cell_range="A1"),
            _violation(sheet="Sheet1", severity="error", cell_range="A2"),
            _violation(sheet="Sheet1", severity="warning", cell_range="B1"),
            _violation(sheet="Sheet2", severity="error", cell_range="C1"),
        ]
        cr = _check_result(vs)
        groups = cr.violation_groups

        # (sheet, severity) が 3 種あること
        assert len(groups) == 3

        # 件数の多い順（Sheet1/error: 2件 が先頭）
        assert groups[0].sheet == "Sheet1"
        assert groups[0].severity == "error"
        assert groups[0].count == 2

        # 残り 2 グループは各 1 件
        remaining_keys = {(g.sheet, g.severity) for g in groups[1:]}
        assert ("Sheet1", "warning") in remaining_keys
        assert ("Sheet2", "error") in remaining_keys

    def test_samples_max_3(self) -> None:
        vs = [_violation(cell_range=f"A{i}") for i in range(10)]
        cr = _check_result(vs)
        groups = cr.violation_groups
        assert len(groups) == 1
        assert len(groups[0].samples) == 3

    def test_samples_all_when_fewer_than_3(self) -> None:
        vs = [_violation(cell_range="A1"), _violation(cell_range="A2")]
        cr = _check_result(vs)
        groups = cr.violation_groups
        assert len(groups[0].samples) == 2

    def test_sorted_by_count_descending(self) -> None:
        vs = [_violation(sheet="Sheet1", severity="warning", cell_range=f"A{i}") for i in range(10)] + [
            _violation(sheet="Sheet1", severity="error", cell_range=f"B{i}") for i in range(3)
        ]
        cr = _check_result(vs)
        groups = cr.violation_groups
        assert groups[0].severity == "warning"
        assert groups[0].count == 10
        assert groups[1].severity == "error"
        assert groups[1].count == 3

    def test_group_count_matches_violations(self) -> None:
        """全グループの件数合計が violations 総数と一致する。"""
        vs = [_violation(sheet="Sheet1", severity="error", cell_range=f"A{i}") for i in range(15)] + [
            _violation(sheet="Sheet2", severity="warning", cell_range=f"B{i}") for i in range(8)
        ]
        cr = _check_result(vs)
        total = sum(g.count for g in cr.violation_groups)
        assert total == len(vs)

    def test_violation_groups_callable_even_below_limit(self) -> None:
        """is_display_truncated が False でも violation_groups は呼び出せる。"""
        vs = [_violation(cell_range=f"A{i}") for i in range(3)]
        cr = _check_result(vs)
        assert cr.is_display_truncated is False
        groups = cr.violation_groups
        assert len(groups) == 1
        assert groups[0].count == 3

    def test_violation_group_model_fields(self) -> None:
        """ViolationGroup の各フィールドが正しく設定される。"""
        vs = [_violation(sheet="MySheet", severity="info", cell_range="Z99")]
        cr = _check_result(vs)
        g: ViolationGroup = cr.violation_groups[0]
        assert g.sheet == "MySheet"
        assert g.severity == "info"
        assert g.count == 1
        assert g.samples[0].cell_range == "Z99"
