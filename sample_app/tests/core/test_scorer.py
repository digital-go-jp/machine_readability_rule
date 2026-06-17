"""LevelScorer のユニットテスト

採点ポリシー:
- confidence == 0 のルールは除外
- 失敗ルールに ``FORCED_ZERO_SEVERITIES``（デフォルト: fatal のみ）が含まれていれば
  そのレベルは強制 0 点
- 上記以外は ``max(0, 100 − 失敗ルールの固定減点合計)``
  減点は ``SEVERITY_DEDUCTIONS[(severity, level)]`` で定義
- 該当ルールがないレベルは未チェック扱い（None）
"""

from __future__ import annotations

import pytest

from harunobu.core.models import (
    AnalysisResult,
    CellRange,
    CheckResult,
    FileMeta,
    MRResult,
    SheetMeta,
    SheetResult,
    TableLayout,
    TableResult,
)
from harunobu.core.scorer import LevelScorer
from harunobu.core.severity import SEVERITY_DEDUCTIONS, Severity


def _check(
    *,
    rule_id: str = "L1-01",
    passed: bool = True,
    severity: Severity = Severity.MAJOR,
    confidence: float = 1.0,
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=passed,
        severity=severity,
        confidence=confidence,
    )


def _sheet_result(
    *,
    name: str = "Sheet1",
    level1: dict[str, CheckResult] | None = None,
    level2: dict[str, CheckResult] | None = None,
    level3: dict[str, CheckResult] | None = None,
) -> SheetResult:
    """単一テーブルを持つ ``SheetResult`` を構築するヘルパ。"""
    mr = MRResult(level1=level1 or {}, level2=level2 or {}, level3=level3 or {})
    return SheetResult(
        sheet_meta=SheetMeta(name=name, used_range="A1:E10"),
        tables=[
            TableResult(
                range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
                layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
                confidence=0.95,
                mr_result=mr,
            ),
        ],
    )


def _analysis(
    *,
    level1: dict[str, CheckResult] | None = None,
    level2: dict[str, CheckResult] | None = None,
    level3: dict[str, CheckResult] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        file_meta=FileMeta(name="test.xlsx", size=1024, format="xlsx", sheet_count=1),
        sheets=[_sheet_result(level1=level1, level2=level2, level3=level3)],
    )


class TestLevelScorerBasic:
    def test_no_rules_returns_none(self):
        """ルール 0 件 → 未チェック（None）"""
        result = _analysis()
        scoring = LevelScorer().score_analysis(result)
        for lv in (1, 2, 3):
            assert scoring.per_level[lv].score is None

    def test_all_pass_returns_100(self):
        """全合格 → 100 点"""
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=True, severity=Severity.FATAL),
                "L1-02": _check(rule_id="L1-02", passed=True, severity=Severity.MAJOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[1].score == 100
        assert scoring.per_level[1].passed == 2
        assert scoring.per_level[1].total == 2
        assert scoring.per_level[1].forced_zero is False

    def test_half_pass_minor_only(self):
        """半数失敗（minor のみ）→ 強制0点にならず固定減点"""
        # Level3 MINOR 失敗: -5点 → 100-5=95
        result = _analysis(
            level3={
                "L3-08": _check(rule_id="L3-08", passed=True, severity=Severity.MINOR),
                "L3-09": _check(rule_id="L3-09", passed=False, severity=Severity.MINOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[3].score == 95
        assert scoring.per_level[3].forced_zero is False
        assert scoring.per_level[1].score is None

    def test_three_of_four_pass(self):
        """4ルール中3合格（Level2 MINOR 1件失敗）→ 100-10=90点"""
        # Level2 MINOR 失敗: -10点
        result = _analysis(
            level2={
                "L2-01": _check(rule_id="L2-01", passed=True, severity=Severity.MINOR),
                "L2-02": _check(rule_id="L2-02", passed=True, severity=Severity.MINOR),
                "L2-03": _check(rule_id="L2-03", passed=True, severity=Severity.MINOR),
                "L2-04": _check(rule_id="L2-04", passed=False, severity=Severity.MINOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[2].score == 90


class TestForcedZero:
    def test_fatal_fail_forces_zero(self):
        """fatal ルール 1 件失敗 → 強制 0 点（デフォルトポリシー）"""
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=False, severity=Severity.FATAL),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[1].score == 0
        assert scoring.per_level[1].forced_zero is True

    def test_critical_fail_does_not_force_zero(self):
        """critical ルール失敗 → 強制 0 点にはならず固定減点（Level1 CRITICAL: -10点）"""
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=True, severity=Severity.FATAL),
                "L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        ls = scoring.per_level[1]
        assert ls.score == 90  # 100 - 10(CRITICAL@L1) = 90
        assert ls.forced_zero is False
        assert {fr.rule_id for fr in ls.failed_rules} == {"L1-03"}

    def test_major_fail_does_not_force_zero(self):
        """major ルール失敗 → 強制 0 点にはならず固定減点（Level3 MAJOR: -10点）"""
        result = _analysis(
            level3={
                "L3-04": _check(rule_id="L3-04", passed=False, severity=Severity.MAJOR),
                "L3-08": _check(rule_id="L3-08", passed=True, severity=Severity.MINOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[3].score == 90  # 100 - 10(MAJOR@L3) = 90
        assert scoring.per_level[3].forced_zero is False

    def test_minor_fail_does_not_force_zero(self):
        """minor のみの失敗 → 強制 0 点にならない（Level3 MINOR: -5点）"""
        result = _analysis(
            level3={
                "L3-08": _check(rule_id="L3-08", passed=False, severity=Severity.MINOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[3].score == 95  # 100 - 5(MINOR@L3) = 95
        assert scoring.per_level[3].forced_zero is False

    def test_info_fail_does_not_force_zero(self):
        """info のみの失敗 → 強制 0 点にならず、減点も 0"""
        result = _analysis(
            level3={
                "L3-08": _check(rule_id="L3-08", passed=False, severity=Severity.INFO),
                "L3-09": _check(rule_id="L3-09", passed=True, severity=Severity.MINOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[3].score == 100  # INFO 減点=0 → 100-0=100
        assert scoring.per_level[3].forced_zero is False


class TestConfidenceFilter:
    def test_zero_confidence_excluded(self):
        """confidence=0 のルールは集計から除外される"""
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=True, severity=Severity.FATAL, confidence=1.0),
                "L1-09": _check(rule_id="L1-09", passed=False, severity=Severity.FATAL, confidence=0.0),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        # confidence=0 は除外なので、L1-09 の失敗は無視されて 100 点
        assert scoring.per_level[1].score == 100
        assert scoring.per_level[1].forced_zero is False
        assert scoring.per_level[1].total == 1

    def test_low_confidence_still_counts(self):
        """confidence>0 なら集計に含まれる（confidence は重み付けに使わない）"""
        result = _analysis(
            level1={
                "L1-09": _check(rule_id="L1-09", passed=False, severity=Severity.FATAL, confidence=0.5),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[1].score == 0
        assert scoring.per_level[1].forced_zero is True


class TestExplainability:
    def test_failed_rules_include_all_failures(self):
        """failed_rules に強制0点要因と非要因の両方が記録される"""
        result = _analysis(
            level2={
                "L2-01": _check(rule_id="L2-01", passed=False, severity=Severity.FATAL),
                "L2-05": _check(rule_id="L2-05", passed=False, severity=Severity.MINOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        ls = scoring.per_level[2]
        failed_ids = {fr.rule_id for fr in ls.failed_rules}
        assert failed_ids == {"L2-01", "L2-05"}
        forced_ids = {fr.rule_id for fr in ls.forced_zero_rules}
        assert forced_ids == {"L2-01"}

    def test_is_any_forced_zero(self):
        """is_any_forced_zero がいずれかのレベルで True になる"""
        result = _analysis(
            level1={"L1-01": _check(rule_id="L1-01", passed=False, severity=Severity.FATAL)},
            level2={"L2-05": _check(rule_id="L2-05", passed=False, severity=Severity.MINOR)},
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.is_any_forced_zero() is True


class TestForcedZeroPolicyOverride:
    """``forced_zero_severities`` のカスタマイズ動作。"""

    def test_empty_frozenset_disables_forced_zero(self):
        """空集合を渡せば「強制 0 点ポリシー無効」になる（None とは区別される）。

        FATAL を forced_zero から外す場合は severity_deductions にも FATAL を追加する必要がある。
        """
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=False, severity=Severity.FATAL),
                "L1-02": _check(rule_id="L1-02", passed=True, severity=Severity.FATAL),
            }
        )
        custom_deductions = {**SEVERITY_DEDUCTIONS, (Severity.FATAL, 1): 20}
        scoring = LevelScorer(
            forced_zero_severities=frozenset(),
            severity_deductions=custom_deductions,
        ).score_analysis(result)
        assert scoring.per_level[1].score == 80  # 100 - 20（FATAL 1件失敗）
        assert scoring.per_level[1].forced_zero is False

    def test_undefined_severity_in_deductions_raises(self):
        """severity_deductions に未定義の severity が来ると KeyError を送出する。"""
        result = _analysis(level1={"L1-01": _check(rule_id="L1-01", passed=False, severity=Severity.FATAL)})

        with pytest.raises(KeyError):
            LevelScorer(forced_zero_severities=frozenset()).score_analysis(result)

    def test_custom_policy_includes_critical(self):
        """CRITICAL も強制 0 点とするカスタムポリシーが有効。"""
        result = _analysis(level1={"L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL)})
        scoring = LevelScorer(forced_zero_severities=frozenset({Severity.FATAL, Severity.CRITICAL})).score_analysis(
            result
        )
        assert scoring.per_level[1].score == 0
        assert scoring.per_level[1].forced_zero is True

    def test_none_falls_back_to_default(self):
        """``None`` を渡すとデフォルト ``FORCED_ZERO_SEVERITIES`` が使われる。"""
        result = _analysis(level1={"L1-01": _check(rule_id="L1-01", passed=False, severity=Severity.FATAL)})
        scoring = LevelScorer(forced_zero_severities=None).score_analysis(result)
        assert scoring.per_level[1].score == 0
        assert scoring.per_level[1].forced_zero is True


class TestGranularity:
    """集計粒度（テーブル / シート / ファイル）。"""

    def test_score_mr_result_for_single_table(self):
        """``score_mr_result`` は 1 テーブル分のみ集計する。"""
        mr = MRResult(
            level1={"L1-01": _check(rule_id="L1-01", passed=True, severity=Severity.FATAL)},
        )
        scoring = LevelScorer().score_mr_result(mr)
        assert scoring.per_level[1].score == 100
        assert scoring.per_level[2].score is None

    def test_score_sheet_result_aggregates_tables_in_sheet(self):
        """``score_sheet_result`` は 1 シート内の全テーブルを集計する。

        Level1 FATAL(pass) + MINOR(fail): MINOR@L1 = -2点 → 100-2=98点。
        """
        mr1 = MRResult(level1={"L1-01": _check(rule_id="L1-01", passed=True, severity=Severity.FATAL)})
        mr2 = MRResult(level1={"L1-02": _check(rule_id="L1-02", passed=False, severity=Severity.MINOR)})
        sheet = SheetResult(
            sheet_meta=SheetMeta(name="Sheet1", used_range="A1:E20"),
            tables=[
                TableResult(
                    range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
                    layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
                    confidence=0.9,
                    mr_result=mr1,
                ),
                TableResult(
                    range=CellRange(start_row=11, start_col=1, end_row=20, end_col=5),
                    layout=TableLayout(header_rows=[11], body_start_row=12, body_end_row=20),
                    confidence=0.9,
                    mr_result=mr2,
                ),
            ],
        )
        scoring = LevelScorer().score_sheet_result(sheet)
        assert scoring.per_level[1].score == 98  # 100 - 2(MINOR@L1) = 98
        assert scoring.per_level[1].total == 2

    def test_sheet_vs_file_aggregation_differs(self):
        """個別シートとファイル全体で集計結果が変わる。

        データシート 1 (Sheet1) が満点、注釈シート 2 (Sheet2) が FATAL 失敗の場合:
        - Sheet1 単体は score=100
        - Sheet2 単体は強制 0 点
        - ファイル全体は強制 0 点（低い方に合わせる挙動を明示）
        """
        good_sheet = _sheet_result(
            name="Sheet1",
            level1={"L1-01": _check(passed=True, severity=Severity.FATAL)},
        )
        bad_sheet = _sheet_result(
            name="Sheet2",
            level1={"L1-01": _check(passed=False, severity=Severity.FATAL)},
        )
        analysis = AnalysisResult(
            file_meta=FileMeta(name="multi.xlsx", size=2048, format="xlsx", sheet_count=2),
            sheets=[good_sheet, bad_sheet],
        )
        scorer = LevelScorer()

        good_score = scorer.score_sheet_result(good_sheet)
        bad_score = scorer.score_sheet_result(bad_sheet)
        file_score = scorer.score_analysis(analysis)

        assert good_score.per_level[1].score == 100
        assert good_score.per_level[1].forced_zero is False

        assert bad_score.per_level[1].score == 0
        assert bad_score.per_level[1].forced_zero is True

        # ファイル全体は片方でも FATAL 失敗があれば強制 0 点
        assert file_score.per_level[1].score == 0
        assert file_score.per_level[1].forced_zero is True


class TestSeverityCoercion:
    """severity 未設定（None）の挙動。"""

    def test_none_severity_treated_as_major(self):
        """``severity=None`` の CheckResult は ``effective_severity == MAJOR`` として扱う。

        Level1 MAJOR 失敗: -5点 → 100-5=95点。
        """
        result = _analysis(
            level1={
                "L1-09": CheckResult(rule_id="L1-09", passed=False, severity=None, confidence=1.0),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        ls = scoring.per_level[1]
        # MAJOR@L1 の減点は 5点
        assert ls.score == 95
        assert ls.forced_zero is False
        # FailedRule の severity は MAJOR にフォールバック
        assert ls.failed_rules[0].severity == Severity.MAJOR


class TestSeverityFixedDeduction:
    """固定減点方式の検証。"""

    def test_single_critical_l1_deducts_10(self):
        """Level1 CRITICAL 1件失敗 → 100-10=90点"""
        result = _analysis(level1={"L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL)})
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[1].score == 90

    def test_single_major_l2_deducts_30(self):
        """Level2 MAJOR 1件失敗 → 100-30=70点"""
        result = _analysis(level2={"L2-05": _check(rule_id="L2-05", passed=False, severity=Severity.MAJOR)})
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[2].score == 70

    def test_multiple_failures_accumulate(self):
        """Level1 CRITICAL×2 + MAJOR×1 失敗 → 100-10-10-5=75点"""
        result = _analysis(
            level1={
                "L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL),
                "L1-05": _check(rule_id="L1-05", passed=False, severity=Severity.CRITICAL),
                "L1-04": _check(rule_id="L1-04", passed=False, severity=Severity.MAJOR),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[1].score == 75  # 100 - 10 - 10 - 5 = 75

    def test_deduction_floors_at_zero(self):
        """減点合計が100を超えても score=0 になる（負にはならない）"""
        # カスタム減点テーブルで故意に大きな減点を設定
        big_deductions = {(Severity.CRITICAL, 1): 60, (Severity.MAJOR, 1): 60}
        result = _analysis(
            level1={
                "L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL),
                "L1-04": _check(rule_id="L1-04", passed=False, severity=Severity.MAJOR),
            }
        )
        scoring = LevelScorer(severity_deductions=big_deductions).score_analysis(result)
        assert scoring.per_level[1].score == 0  # max(0, 100-120) = 0

    def test_info_failure_no_deduction(self):
        """INFO 失敗のみ → 減点 0 → score=100"""
        result = _analysis(level1={"L1-09": _check(rule_id="L1-09", passed=False, severity=Severity.INFO)})
        scoring = LevelScorer().score_analysis(result)
        assert scoring.per_level[1].score == 100

    def test_fatal_excluded_from_deduction(self):
        """FATAL が全合格のとき、採点は非 FATAL ルールのみで行われる"""
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=True, severity=Severity.FATAL),
                "L1-02": _check(rule_id="L1-02", passed=True, severity=Severity.FATAL),
                "L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL),
            }
        )
        scoring = LevelScorer().score_analysis(result)
        # FATAL 2件は通過、CRITICAL 1件失敗: 100-10=90
        assert scoring.per_level[1].score == 90
        assert scoring.per_level[1].forced_zero is False

    def test_custom_deductions_applied(self):
        """severity_deductions カスタマイズが反映される"""
        # 全て重み均等 (=1点) にすると、CRITICAL も MAJOR も同等の減点になる
        flat_deductions = {
            (Severity.CRITICAL, 1): 10,
            (Severity.MAJOR, 1): 10,
            (Severity.MINOR, 1): 10,
        }
        result = _analysis(
            level1={
                "L1-03": _check(rule_id="L1-03", passed=False, severity=Severity.CRITICAL),
                "L1-04": _check(rule_id="L1-04", passed=True, severity=Severity.MAJOR),
            }
        )
        scoring = LevelScorer(severity_deductions=flat_deductions).score_analysis(result)
        assert scoring.per_level[1].score == 90  # 100 - 10(CRITICAL) = 90
