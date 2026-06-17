"""L2-05: 選択肢列と「その他」の詳細記入が分離されているか — sample_by_mr_rules サンプルによる検証

サンプル: rule_20_split_other.xlsx（1ファイル3シート構成、各50行）

  OK    — No / 設問1 / 設問1: その他の事由 の3列。
          設問1は「1. 取組済」「2. 取組予定」「3. 未定」「4. その他」で統一。
          「4. その他」は 1種類のみ → 条件1（2種類以上）不成立 → 違反なし
          → passed=True, violations=0

  NG-01 — No / 設問1 の2列。
          「4. その他: {詳細}」形式で詳細を同一セルに混在（6種類×各1回）。
          「4. その他: {詳細}」6種 が count=1 < _OTHER_MIN_COUNT=3 → 全件検出。
          → passed=False, violations >= 6

  NG-02 — No / 設問1 の2列。
          全選択肢が先頭スペース付き。「 その他: {詳細}」形式で混在（5種類×各1回）。
          先頭スペース付き値も「その他」を含むため検出される。
          → passed=False, violations >= 5
"""

from __future__ import annotations

import os

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    get_rule_results_by_sheet,
)

RULE_ID = "L2-05"
SAMPLE_STEM = "rule_20_split_other"


@pytest.fixture(scope="module", autouse=True)
def disable_ai():
    """AI を無効化して統計的チェックのみで検証する。"""
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
    """各シートの L2-05 CheckResult を返す。"""
    analysis = analyze_file(sample_path)
    by_sheet = get_rule_results_by_sheet(analysis, RULE_ID)
    if not by_sheet:
        pytest.skip(f"{RULE_ID} の結果がありません（全列スキップ等）")
    return by_sheet


class TestOK:
    """OK シート: 設問1が「4. その他」1種類のみ → 条件1不成立 → 合格"""

    def test_ok_sheet_passes(self, results_by_sheet):
        assert "OK" in results_by_sheet, "OK シートの結果が見つかりません"
        result = results_by_sheet["OK"][0]
        assert result["passed"] is True, (
            f"OK シートで不合格: severity={result['severity']}, violations={result['violation_count']}"
        )

    def test_ok_sheet_no_violations(self, results_by_sheet):
        result = results_by_sheet["OK"][0]
        assert result["violation_count"] == 0

    def test_ok_sheet_has_positive_confidence(self, results_by_sheet):
        """選択肢列として分析が実行された（confidence > 0）ことを確認する。"""
        result = results_by_sheet["OK"][0]
        assert result["check_result"].confidence > 0


class TestNG01:
    """NG-01 シート: 「4. その他: {詳細}」形式で6種類が各1回混在 → 不合格

    サンプルの NG-01 では「4. その他: 対象となる事務を他団体に委託しているため」等、
    6種類の詳細混在値が各1回出現する。count=1 < _OTHER_MIN_COUNT=3 のため全件検出。
    """

    def test_ng01_fails(self, results_by_sheet):
        assert "NG-01" in results_by_sheet, "NG-01 シートの結果が見つかりません"
        result = results_by_sheet["NG-01"][0]
        assert result["passed"] is False, f"NG-01 シートは不合格であるべきです (severity={result['severity']})"

    def test_ng01_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-01"][0]
        assert result["violation_count"] >= 6

    def test_ng01_violations_are_warnings(self, results_by_sheet):
        """統計的検出の違反 severity は warning。"""
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert all(v.severity == "warning" for v in cr.violations)

    def test_ng01_violation_describes_other_mixing(self, results_by_sheet):
        """違反メッセージが「その他」の詳細混在を示す形式になっている。"""
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert any("その他" in v.description and "可能性" in v.description for v in cr.violations)

    def test_ng01_score_reduced(self, results_by_sheet):
        result = results_by_sheet["NG-01"][0]
        assert result["passed"] is False

    def test_ng01_number_prefixed_pattern_detected(self, results_by_sheet):
        """「4. その他: 詳細」形式（番号プレフィックス付き）が検出される。

        旧実装では ^ 始まりの正規表現にマッチしないため検出できなかったパターン。
        """
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert any("4. その他:" in v.description for v in cr.violations)


class TestNG02:
    """NG-02 シート: 先頭スペース付き「 その他: {詳細}」形式で5種類が各1回混在 → 不合格

    NG-02 では row 26 の「その他」を「取組済」に差し替えているため
    「その他」混在は5種類（NG-01 の6種類より1件少ない）。
    先頭スペースがあっても「その他」を含むため検出される。
    """

    def test_ng02_fails(self, results_by_sheet):
        assert "NG-02" in results_by_sheet, "NG-02 シートの結果が見つかりません"
        result = results_by_sheet["NG-02"][0]
        assert result["passed"] is False, f"NG-02 シートは不合格であるべきです (severity={result['severity']})"

    def test_ng02_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-02"][0]
        assert result["violation_count"] >= 5

    def test_ng02_violations_are_warnings(self, results_by_sheet):
        cr = results_by_sheet["NG-02"][0]["check_result"]
        assert all(v.severity == "warning" for v in cr.violations)

    def test_ng02_leading_space_pattern_detected(self, results_by_sheet):
        """先頭スペース付き「 その他: 詳細」形式が検出される。"""
        cr = results_by_sheet["NG-02"][0]["check_result"]
        assert any("その他" in v.description for v in cr.violations)

    def test_ng02_fewer_violations_than_ng01(self, results_by_sheet):
        """NG-02 は row 26 の差し替えにより NG-01 より違反が少ない（5件 vs 6件）。"""
        ng01_count = results_by_sheet["NG-01"][0]["violation_count"]
        ng02_count = results_by_sheet["NG-02"][0]["violation_count"]
        assert ng02_count <= ng01_count, f"NG-02({ng02_count}件) は NG-01({ng01_count}件) 以下の違反であるべきです"
