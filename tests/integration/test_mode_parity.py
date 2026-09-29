"""統合テスト: --mode と評価対象レベルの整合性

回帰テスト。以前は ``Config(mode=...)`` が mode から ``mr_levels`` を導出せず、
ファイルベースの ``analyze(path, Config(mode=...))``（CLI 経路）が常に既定の
``{1, 2}`` を評価していた。その結果:

- ``--mode thorough`` で Level 3 が黙ってスキップされる
- ``--mode lite`` で Level 2 まで過剰評価される

本テストは mode が評価対象レベルを決定し、SDK 経路（``Analyzer(mode)``）と
ファイルベース経路（``analyze(path, Config(mode=...))``）が一致することを保証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harunobu.core.analyzer import Analyzer, analyze
from harunobu.core.models import _MODE_LEVELS, AnalysisResult, Config

# ルール検証用の実サンプル（複数レベルのルールが結果を返す xlsx）
_SAMPLE = Path(__file__).parent.parent / "sample_by_mr_rules" / "samples" / "rule_12_merged_cells.xlsx"

# mode → 期待する評価対象レベル集合
_EXPECTED: dict[str, set[int]] = {
    "lite": {1},
    "standard": {1, 2},
    "thorough": {1, 2, 3},
}


def _evaluated_levels(result: AnalysisResult) -> set[int]:
    """採点結果から、実際に1件以上のルール結果が出たレベルの集合を返す。"""
    levels: set[int] = set()
    for sheet in result.sheets:
        for table in sheet.tables:
            mr = table.mr_result
            if mr.level1:
                levels.add(1)
            if mr.level2:
                levels.add(2)
            if mr.level3:
                levels.add(3)
    return levels


class TestModeDerivesLevels:
    """Config が mode から mr_levels を導出することを確認する。"""

    @pytest.mark.parametrize(("mode", "expected"), list(_EXPECTED.items()))
    def test_config_derives_mr_levels_from_mode(self, mode: str, expected: set[int]):
        """Config(mode=...) は mode に対応する mr_levels を導出する。"""
        assert Config(mode=mode).mr_levels == expected  # type: ignore[arg-type]

    def test_default_config_uses_standard_levels(self):
        """既定（mode=standard）では {1, 2} を評価する。"""
        assert Config().mr_levels == {1, 2}

    def test_explicit_mr_levels_overrides_mode(self):
        """mr_levels を明示指定した場合は mode から導出せずそれを尊重する。"""
        assert Config(mode="thorough", mr_levels={1}).mr_levels == {1}
        assert Config(mode="lite", mr_levels={1, 2, 3}).mr_levels == {1, 2, 3}

    def test_mode_levels_is_single_source_of_truth(self):
        """_MODE_LEVELS が期待値と一致する（マッピングの単一定義を確認）。"""
        assert _MODE_LEVELS == _EXPECTED


class TestAnalyzerEvaluatesCorrectLevels:
    """SDK 経路とファイルベース経路が同じレベルを評価することを確認する。"""

    @pytest.mark.parametrize(("mode", "expected"), list(_EXPECTED.items()))
    def test_analyzer_evaluates_correct_levels(self, mode: str, expected: set[int]):
        """Analyzer(mode) と analyze(Config(mode=...)) が同一の mr_levels を持つ。"""
        # SDK 経路（UI が使う Analyzer クラス）
        assert Analyzer(mode)._config.mr_levels == expected
        # ファイルベース経路（CLI の cmd_analyze が使う Config(mode=...)）
        assert Config(mode=mode).mr_levels == expected  # type: ignore[arg-type]


class TestModeLevelsEndToEnd:
    """実ファイルを analyze() で採点し、評価レベルが mode と一致することを確認する。"""

    def test_lite_evaluates_only_level1(self):
        """lite は Level 1 のみ（回帰: 以前は Level 2 まで過剰評価していた）。"""
        result = analyze(_SAMPLE, Config(mode="lite"))
        assert _evaluated_levels(result) == {1}

    def test_standard_evaluates_level1_and_2_only(self):
        """standard は Level 1・2 のみで Level 3 は評価しない。"""
        evaluated = _evaluated_levels(analyze(_SAMPLE, Config(mode="standard")))
        assert 2 in evaluated
        assert 3 not in evaluated

    def test_thorough_evaluates_level3(self):
        """thorough は Level 3 を評価する（回帰: 以前は黙ってスキップされていた）。"""
        evaluated = _evaluated_levels(analyze(_SAMPLE, Config(mode="thorough")))
        assert 3 in evaluated
