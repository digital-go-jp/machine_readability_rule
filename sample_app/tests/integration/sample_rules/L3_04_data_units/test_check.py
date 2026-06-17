"""L3-04: データの単位を記載しているか — サンプルファイルによる検証

サンプル: rule_25_data_units.xlsx（1ファイル4シート構成）

  OK         — 全数値列に括弧付き単位を明記 → passed=True
  OK-Implied — 単位を暗示する語のみ（人口/金額/年齢） → passed=True
  NG-01      — 数値列ヘッダーに単位がなく暗示語にも該当しない（全列違反） → passed=False
  NG-02      — 一部の列だけ単位欠落（混在ケース） → passed=False かつ
               違反対象は単位欠落列のみで、単位ありの列は検出されない
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harunobu.core.analyzer import Analyzer
from harunobu.core.models import AnalysisResult
from harunobu.core.reader import read_file
from tests.integration.sample_rules.conftest import get_rule_results_by_sheet

RULE_ID = "L3-04"
SAMPLE_STEM = "rule_25_data_units"


@pytest.fixture(autouse=True)
def disable_ai(monkeypatch):
    """AI 補完を無効化し、決定論パスのみを検証する。"""
    monkeypatch.setenv("HARUNOBU_AI_DISABLED", "1")


def _analyze_thorough(path: Path) -> AnalysisResult:
    """L3 を含む thorough モードでファイルを分析する。"""
    workbook = read_file(path)
    analyzer = Analyzer(mode="thorough")
    return analyzer.analyze(workbook)


@pytest.fixture(scope="module")
def sample_path(samples_dir):
    path = samples_dir / f"{SAMPLE_STEM}.xlsx"
    if not path.exists():
        pytest.skip(f"サンプルが見つかりません: {path}")
    return path


@pytest.fixture
def results_by_sheet(sample_path):
    """各シートの L3-04 CheckResult を返す。"""
    analysis = _analyze_thorough(sample_path)
    by_sheet = get_rule_results_by_sheet(analysis, RULE_ID)
    if not by_sheet:
        pytest.skip(f"{RULE_ID} の結果がありません")
    return by_sheet


class TestOK:
    """OK シート: 全数値列に括弧付き単位 → 合格"""

    def test_ok_sheet_passes(self, results_by_sheet):
        assert "OK" in results_by_sheet, "OK シートの結果が見つかりません"
        result = results_by_sheet["OK"][0]
        assert result["passed"] is True, (
            f"OK シートで不合格: severity={result['severity']}, violations={result['violation_count']}"
        )

    def test_ok_sheet_no_violations(self, results_by_sheet):
        result = results_by_sheet["OK"][0]
        assert result["violation_count"] == 0


class TestOKImplied:
    """OK-Implied シート: 単位暗示語（人口・金額・年齢）のみ → 合格"""

    def test_ok_implied_sheet_passes(self, results_by_sheet):
        assert "OK-Implied" in results_by_sheet, "OK-Implied シートの結果が見つかりません"
        result = results_by_sheet["OK-Implied"][0]
        assert result["passed"] is True, (
            f"OK-Implied シートで不合格: severity={result['severity']}, violations={result['violation_count']}"
        )

    def test_ok_implied_no_violations(self, results_by_sheet):
        result = results_by_sheet["OK-Implied"][0]
        assert result["violation_count"] == 0


class TestNG01:
    """NG-01 シート: 全数値列ヘッダーが単位不明 → 不合格"""

    def test_ng01_fails(self, results_by_sheet):
        assert "NG-01" in results_by_sheet, "NG-01 シートの結果が見つかりません"
        result = results_by_sheet["NG-01"][0]
        assert result["passed"] is False, "NG-01 シートは不合格であるべきです"

    def test_ng01_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-01"][0]
        assert result["violation_count"] >= 1

    def test_ng01_violation_message_mentions_unit(self, results_by_sheet):
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert any("単位" in v.description for v in cr.violations), "単位欠落の違反メッセージが含まれていません"


class TestNG02:
    """NG-02 シート: 一部の列だけ単位欠落 → 不合格・対象列のみ違反"""

    def test_ng02_fails(self, results_by_sheet):
        assert "NG-02" in results_by_sheet, "NG-02 シートの結果が見つかりません"
        result = results_by_sheet["NG-02"][0]
        assert result["passed"] is False, "NG-02 シートは不合格であるべきです"

    def test_ng02_violation_targets_only_missing_unit_column(self, results_by_sheet):
        cr = results_by_sheet["NG-02"][0]["check_result"]
        # 「数量」だけが単位欠落 → 違反は 1 件、対象列名「数量」のみ
        descriptions = [v.description for v in cr.violations]
        assert len(descriptions) == 1, f"単位欠落列が1つのケースで違反数が想定外: {descriptions}"
        assert "数量" in descriptions[0], f"単位欠落列「数量」の違反メッセージが含まれていません: {descriptions[0]}"
        # 単位ありの列が誤検出されていないこと
        assert "売上" not in descriptions[0]
        assert "面積" not in descriptions[0]
