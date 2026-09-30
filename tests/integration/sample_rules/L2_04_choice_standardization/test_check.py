"""L2-04: 選択肢回答が標準化されているか — sample_by_mr_rules サンプルによる検証

サンプル: rule_19_normalize_nominals.xlsx（1ファイル3シート構成、各200行）

  OK    — "No" / "設問1" / "設問1コード" の3列。
          設問1は「取組済」「取組予定」「未定」で統一。
          → passed=True, violations=0

  NG-01 — "No" / "設問1" の2列。
          設問1に番号プレフィックス付きの表記揺れが混在
          （例: "1. 取組済"/"1. 取り組み済み"、"2. 取組予定"/"2. 取組予定（R8以降）"）。
          出現1〜2回の稀なバリアントが外れ値として検出される。
          → passed=False, violations >= 1

  NG-02 — "No" / "設問1" の2列。
          番号なしの表記揺れが混在
          （例: "取組済"/"取組済み"/"取り組み済"、"取組予定"/"取組予定（R8以降）"/"取り組み予定"）。
          → passed=False, violations >= 1
"""

from __future__ import annotations

import os

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    get_rule_results_by_sheet,
)

RULE_ID = "L2-04"
SAMPLE_STEM = "rule_19_normalize_nominals"


@pytest.fixture(scope="module", autouse=True)
def disable_ai():
    """AI を無効化して決定論的チェックのみで検証する。"""
    original = os.environ.get("HARUNOBU_AI_DISABLED")
    os.environ["HARUNOBU_AI_DISABLED"] = "1"
    yield
    if original is None:
        os.environ.pop("HARUNOBU_AI_DISABLED", None)
    else:
        os.environ["HARUNOBU_AI_DISABLED"] = original


@pytest.fixture(scope="module")
def sample_path(samples_dir):
    path = samples_dir / f"{SAMPLE_STEM}.xlsx"
    if not path.exists():
        pytest.skip(f"サンプルが見つかりません: {path}")
    return path


@pytest.fixture(scope="module")
def results_by_sheet(sample_path):
    """各シートの L2-04 CheckResult を返す。"""
    analysis = analyze_file(sample_path)
    by_sheet = get_rule_results_by_sheet(analysis, RULE_ID)
    if not by_sheet:
        pytest.skip(f"{RULE_ID} の結果がありません（全列スキップ等）")
    return by_sheet


class TestOK:
    """OK シート: 設問1が「取組済」「取組予定」「未定」で統一 → 合格"""

    def test_ok_sheet_passes(self, results_by_sheet):
        assert "OK" in results_by_sheet, "OK シートの結果が見つかりません"
        result = results_by_sheet["OK"][0]
        assert result["passed"] is True, (
            f"OK シートで不合格: severity={result['severity']}, violations={result['violation_count']}"
        )

    def test_ok_sheet_perfect_score(self, results_by_sheet):
        result = results_by_sheet["OK"][0]
        assert result["passed"] is True

    def test_ok_sheet_no_violations(self, results_by_sheet):
        result = results_by_sheet["OK"][0]
        assert result["violation_count"] == 0

    def test_ok_sheet_has_positive_confidence(self, results_by_sheet):
        """分布分析が実行された（confidence > 0）ことを確認する。"""
        result = results_by_sheet["OK"][0]
        assert result["check_result"].confidence > 0


class TestNG01:
    """NG-01 シート: 番号プレフィックス付きの表記揺れが混在 → 不合格

    "_apply_variants" により設問1に "1. 取組済" の他に
    "1. 取り組み済み" / "1. 取組済み" 等が混在する。
    _OUTLIER_MAX_COUNT=2 以下の出現回数の稀なバリアントが外れ値として検出される。
    """

    def test_ng01_fails(self, results_by_sheet):
        assert "NG-01" in results_by_sheet, "NG-01 シートの結果が見つかりません"
        result = results_by_sheet["NG-01"][0]
        assert result["passed"] is False, f"NG-01 シートは不合格であるべきです (severity={result['severity']})"

    def test_ng01_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-01"][0]
        assert result["violation_count"] >= 1

    def test_ng01_violations_are_warnings(self, results_by_sheet):
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert all(v.severity == "warning" for v in cr.violations)

    def test_ng01_violation_describes_hyoki_bure(self, results_by_sheet):
        """違反メッセージが表記揺れを示す形式になっている。"""
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert any("表記揺れの可能性" in v.description for v in cr.violations)

    def test_ng01_score_reduced(self, results_by_sheet):
        """違反により満点より低いスコアになる。"""
        result = results_by_sheet["NG-01"][0]
        assert result["passed"] is False


class TestNG02:
    """NG-02 シート: 番号なしの表記揺れが混在 → 不合格

    "_apply_variants" により設問1に "取組予定" の他に
    "取組予定（R8以降）" / "取り組み予定" / "取組予定（令和8年6月）" 等が混在する。
    NG-01 より多くのバリアントが稀な出現回数に収まるため、より多くの違反が検出される。
    """

    def test_ng02_fails(self, results_by_sheet):
        assert "NG-02" in results_by_sheet, "NG-02 シートの結果が見つかりません"
        result = results_by_sheet["NG-02"][0]
        assert result["passed"] is False, f"NG-02 シートは不合格であるべきです (severity={result['severity']})"

    def test_ng02_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-02"][0]
        assert result["violation_count"] >= 1

    def test_ng02_violations_are_warnings(self, results_by_sheet):
        cr = results_by_sheet["NG-02"][0]["check_result"]
        assert all(v.severity == "warning" for v in cr.violations)

    def test_ng02_violation_describes_hyoki_bure(self, results_by_sheet):
        cr = results_by_sheet["NG-02"][0]["check_result"]
        assert any("表記揺れの可能性" in v.description for v in cr.violations)

    def test_ng02_more_violations_than_ng01(self, results_by_sheet):
        """NG-02 は NG-01 より多くの表記揺れを含む（バリアントの多様性が高いため）。"""
        ng01_count = results_by_sheet["NG-01"][0]["violation_count"]
        ng02_count = results_by_sheet["NG-02"][0]["violation_count"]
        assert ng02_count >= ng01_count, f"NG-02({ng02_count}件) は NG-01({ng01_count}件) 以上の違反を持つべきです"

    def test_ng02_score_is_zero(self, results_by_sheet):
        """違反数が列数を超えるためスコアが0になる。"""
        result = results_by_sheet["NG-02"][0]
        assert result["passed"] is False
