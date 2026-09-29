"""レベル別スコアリング

ルールチェック（``RuleBase.check``）の結果を集約し、各レベル（L1/L2/L3）の
スコアを算出する。スコアリング・ポリシーは本モジュールに閉じ、ルール側は
ポリシーを知らない（ルール自身は OK/NG と severity のみを返す）。

スコア算出ルール:

1. ``confidence == 0`` のルール（未実行・エラー）は対象外
2. 失敗ルールに ``FORCED_ZERO_SEVERITIES``（デフォルト: fatal のみ）が含まれていれば
   そのレベルは **強制 0 点**
3. 上記以外は ``max(0, 100 − 失敗ルールの固定減点合計)``
   減点は ``SEVERITY_DEDUCTIONS[(severity, level)]`` で定義（INFO は 0 点）
4. 該当ルールが 1 件もないレベルは ``score=None``（未チェック）

集計粒度:

- :py:meth:`LevelScorer.score_mr_result` — 1 テーブル単位（``MRResult``）
- :py:meth:`LevelScorer.score_sheet_result` — 1 シート単位（``SheetResult`` の全テーブル）
- :py:meth:`LevelScorer.score_analysis` — ファイル全体（``AnalysisResult`` の全シート）

入力 Excel に注釈シート・グラフ用シートが混在するケースでは、データシートだけを
:py:meth:`score_sheet_result` で個別に評価できる。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from harunobu.core.models import AnalysisResult, CheckResult, MRResult, SheetResult
from harunobu.core.severity import FORCED_ZERO_SEVERITIES, SEVERITY_DEDUCTIONS, Severity


class FailedRule(BaseModel):
    """失敗したルールの参照情報（説明性のため severity を含む）。"""

    rule_id: str
    severity: Severity


class LevelScore(BaseModel):
    """1 レベル分のスコア結果。

    Attributes:
        level
            1, 2, 3 のいずれか
        score
            0--100 の整数。未チェック時は ``None``
        passed
            合格ルール数（confidence>0 のみカウント）
        total
            評価対象ルール数（confidence>0 のみカウント）
        forced_zero
            強制 0 点が発動したか
        forced_zero_rules
            強制 0 点の原因となったルール（severity 付き）
        failed_rules
            このレベルで失敗したルール全件（強制 0 点要因含む）
    """

    level: int
    score: int | None
    passed: int = 0
    total: int = 0
    forced_zero: bool = False
    forced_zero_rules: list[FailedRule] = Field(default_factory=list)
    failed_rules: list[FailedRule] = Field(default_factory=list)


class LevelScoring(BaseModel):
    """レベル別スコアの集約。"""

    per_level: dict[int, LevelScore] = Field(default_factory=dict)

    def get(self, level: int) -> LevelScore | None:
        """指定レベルのスコアを返す（未チェックなら ``None``）。"""
        return self.per_level.get(level)

    def is_any_forced_zero(self) -> bool:
        """いずれかのレベルで強制 0 点が発動しているかを返す。"""
        return any(ls.forced_zero for ls in self.per_level.values())


class LevelScorer:
    """レベル別スコアを算出するスコアリング・エンジン。

    ポリシー（強制 0 点の severity 集合）は ``forced_zero_severities`` で、
    固定減点テーブルは ``severity_deductions`` で差し替え可能。
    デフォルトはそれぞれ ``FORCED_ZERO_SEVERITIES`` (= FATAL のみ)、
    ``SEVERITY_DEDUCTIONS``。

    ``forced_zero_severities=frozenset()`` を渡せば「強制 0 点なし」のポリシーになる
    （``None`` とは区別される）。
    """

    def __init__(
        self,
        forced_zero_severities: frozenset[Severity] | None = None,
        severity_deductions: dict[tuple[Severity, int], int] | None = None,
    ) -> None:
        self.forced_zero_severities = (
            forced_zero_severities if forced_zero_severities is not None else FORCED_ZERO_SEVERITIES
        )
        self.severity_deductions = severity_deductions if severity_deductions is not None else SEVERITY_DEDUCTIONS

    def score_mr_result(self, mr_result: MRResult) -> LevelScoring:
        """単一の ``MRResult``（1 テーブル分）からレベル別スコアを算出する。"""
        per_level_results: dict[int, list[CheckResult]] = {
            1: list(mr_result.level1.values()),
            2: list(mr_result.level2.values()),
            3: list(mr_result.level3.values()),
        }
        return self._score_per_level(per_level_results)

    def score_sheet_result(self, sheet_result: SheetResult) -> LevelScoring:
        """単一の ``SheetResult``（1 シート分・複数テーブル）からレベル別スコアを算出する。

        データシート単独で評価したいケース（注釈シート・グラフ用シートが
        ファイルに混在しており、データ部分のみを採点したい）で利用する。
        """
        per_level_results: dict[int, list[CheckResult]] = {1: [], 2: [], 3: []}
        for table in sheet_result.tables:
            per_level_results[1].extend(table.mr_result.level1.values())
            per_level_results[2].extend(table.mr_result.level2.values())
            per_level_results[3].extend(table.mr_result.level3.values())
        return self._score_per_level(per_level_results)

    def score_analysis(self, analysis: AnalysisResult) -> LevelScoring:
        """ファイル全体（複数シート・テーブル）の集約スコア。

        全テーブルのチェック結果をレベル単位でフラット化して集計する。
        """
        per_level_results: dict[int, list[CheckResult]] = {1: [], 2: [], 3: []}
        for sheet in analysis.sheets:
            for table in sheet.tables:
                per_level_results[1].extend(table.mr_result.level1.values())
                per_level_results[2].extend(table.mr_result.level2.values())
                per_level_results[3].extend(table.mr_result.level3.values())
        return self._score_per_level(per_level_results)

    def _score_per_level(self, per_level_results: dict[int, list[CheckResult]]) -> LevelScoring:
        out: dict[int, LevelScore] = {}
        for level, results in per_level_results.items():
            out[level] = self._score_level(level, results)
        return LevelScoring(per_level=out)

    def _score_level(self, level: int, results: list[CheckResult]) -> LevelScore:
        active = [r for r in results if r.confidence > 0.0]
        if not active:
            return LevelScore(level=level, score=None)

        passed_count = sum(1 for r in active if r.passed)
        total = len(active)

        failed_rules: list[FailedRule] = [
            FailedRule(rule_id=r.rule_id, severity=r.effective_severity) for r in active if not r.passed
        ]
        forced_zero_rules = [f for f in failed_rules if f.severity in self.forced_zero_severities]

        if forced_zero_rules:
            return LevelScore(
                level=level,
                score=0,
                passed=passed_count,
                total=total,
                forced_zero=True,
                forced_zero_rules=forced_zero_rules,
                failed_rules=failed_rules,
            )

        # 固定減点方式: 失敗した非 forced_zero ルールの減点を積算
        # severity_deductions に未定義の (severity, level) があれば KeyError で即停止する
        deduction = sum(
            self.severity_deductions[(r.effective_severity, level)]
            for r in active
            if not r.passed and r.effective_severity not in self.forced_zero_severities
        )
        score = max(0, 100 - deduction)
        return LevelScore(
            level=level,
            score=score,
            passed=passed_count,
            total=total,
            forced_zero=False,
            forced_zero_rules=[],
            failed_rules=failed_rules,
        )
