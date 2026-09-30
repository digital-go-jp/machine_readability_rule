"""Bulk ルール基盤 — 複数ファイルを横断して評価するルールの基底."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from harunobu.core.models import AnalysisResult, CheckResult, FileMeta


class BulkFileEntry(BaseModel):
    """Bulk 評価で 1 ファイル分の情報をまとめたエントリ."""

    file_name: str
    file_meta: FileMeta
    workbook: Any  # WorkBook（Streamlit 再 import の影響回避）
    analysis: AnalysisResult

    model_config = {"arbitrary_types_allowed": True}


class BulkAnalysisResult(BaseModel):
    """複数ファイル一括分析の結果."""

    files: list[AnalysisResult] = Field(default_factory=list)
    bulk_checks: dict[str, CheckResult] = Field(default_factory=dict)
    """rule_id -> ファイル横断チェック結果."""

    @property
    def file_count(self) -> int:
        """評価対象ファイルの件数を返す。"""
        return len(self.files)

    def per_file_scores(self) -> list[int | None]:
        """各ファイルの平均レベルスコア（L1/L2/L3 のうち未チェック以外の平均）."""
        from harunobu.core.scorer import LevelScorer

        scorer = LevelScorer()
        out: list[int | None] = []
        for analysis in self.files:
            scoring = scorer.score_analysis(analysis)
            level_scores = [ls.score for ls in scoring.per_level.values() if ls.score is not None]
            out.append(round(sum(level_scores) / len(level_scores)) if level_scores else None)
        return out

    @property
    def total_score(self) -> int:
        """各ファイルの平均スコアと bulk チェックの合格率の加重平均.

        ``LevelScorer`` のレベル別スコアを採用し、ファイル単位では未チェックを
        除いた L1/L2/L3 の平均、bulk チェックは ``passed/total`` を 100 点換算する。
        """
        if not self.files:
            return 100
        per_file_scores = [s for s in self.per_file_scores() if s is not None]
        per_file_avg = sum(per_file_scores) / len(per_file_scores) if per_file_scores else 100.0
        if not self.bulk_checks:
            return round(per_file_avg)
        active = [cr for cr in self.bulk_checks.values() if cr.confidence > 0.0]
        if not active:
            return round(per_file_avg)
        bulk_pass_rate = sum(1 for cr in active if cr.passed) / len(active) * 100
        return round(per_file_avg * 0.7 + bulk_pass_rate * 0.3)


class BulkRuleMixin(ABC):
    """複数ファイル横断チェックを行うルールに付与する mixin.

    RuleBase と多重継承して使用する。check_bulk は registry/Analyzer が
    `isinstance(rule, BulkRuleMixin)` で判別して呼び出す。
    """

    @abstractmethod
    def check_bulk(self, files: list[BulkFileEntry]) -> CheckResult:
        """ファイル横断チェックを実行する."""
