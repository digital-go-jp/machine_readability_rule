"""L2-03: 各列が一意に識別可能な項目名を持っているか — サンプルファイルによる検証

サンプル: rule_18_unique_column.xlsx（1ファイル5シート構成）

  OK    — 単一行ヘッダー・全列一意 → passed=True
  NG-01 — 多段ヘッダーで「財務情報」が B-C 列に横結合。
          C 列の親ヘッダーが横結合の従属セルになる → passed=False
  NG-02 — 2行目が単位行で「千円」が B・C 列に重複 → passed=False
  NG-03 — 単一行ヘッダーで A-B 列に横結合（L2 では結合ヘッダー自体を許容しない）→ passed=False
  NG-04 — 親行に複数の横結合グループ（複数のマルチヘッダー＆セル結合）→ passed=False
"""

from __future__ import annotations

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    get_rule_results_by_sheet,
)

RULE_ID = "L2-03"
SAMPLE_STEM = "rule_18_unique_column"


@pytest.fixture(scope="module")
def sample_path(samples_dir):
    path = samples_dir / f"{SAMPLE_STEM}.xlsx"
    if not path.exists():
        pytest.skip(f"サンプルが見つかりません: {path}")
    return path


@pytest.fixture(scope="module")
def results_by_sheet(sample_path):
    """各シートの L2-03 CheckResult を返す。"""
    analysis = analyze_file(sample_path)
    by_sheet = get_rule_results_by_sheet(analysis, RULE_ID)
    if not by_sheet:
        pytest.skip(f"{RULE_ID} の結果がありません")
    return by_sheet


class TestOK:
    """OK シート: 単一行ヘッダーで全列一意 → 合格"""

    def test_ok_sheet_passes(self, results_by_sheet):
        assert "OK" in results_by_sheet, "OK シートの結果が見つかりません"
        result = results_by_sheet["OK"][0]
        assert result["passed"] is True, (
            f"OK シートで不合格: severity={result['severity']}, violations={result['violation_count']}"
        )

    def test_ok_sheet_no_violations_pass(self, results_by_sheet):
        result = results_by_sheet["OK"][0]
        assert result["passed"] is True
        assert result["violation_count"] == 0

    def test_ok_sheet_no_violations(self, results_by_sheet):
        result = results_by_sheet["OK"][0]
        assert result["violation_count"] == 0


class TestNG01:
    """NG-01 シート: 多段ヘッダーで親行が横結合 → 列名が不完全で不合格

    構造:
      Row1: A=空, B="財務情報"(B1:C1 結合マスター), C=従属セル
      Row2: A="会社",  B="売上高",  C="営業利益"
      Data: 行3以降

    C 列の親行 (C1) が横結合の従属セルのため、
    「財務情報_営業利益」という連結名を構成できない → L2-03 違反
    """

    def test_ng01_fails(self, results_by_sheet):
        assert "NG-01" in results_by_sheet, "NG-01 シートの結果が見つかりません"
        result = results_by_sheet["NG-01"][0]
        assert result["passed"] is False, "NG-01 シートは不合格であるべきです"

    def test_ng01_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-01"][0]
        assert result["violation_count"] >= 1

    def test_ng01_violation_describes_incomplete_header(self, results_by_sheet):
        cr = results_by_sheet["NG-01"][0]["check_result"]
        assert any("結合" in v.description for v in cr.violations), (
            "横結合による不完全ヘッダーの違反メッセージが含まれていません"
        )


class TestNG02:
    """NG-02 シート: 単位行に「千円」が重複 → 不合格

    構造:
      Row1: A=空,    B="売上高", C="営業利益"
      Row2: A="会社", B="千円",  C="千円"    ← レイアウト検出では Row2 がヘッダー行
      Data: 行3以降

    B・C 列のヘッダーが共に「千円」で重複 → L2-03 違反
    """

    def test_ng02_fails(self, results_by_sheet):
        assert "NG-02" in results_by_sheet, "NG-02 シートの結果が見つかりません"
        result = results_by_sheet["NG-02"][0]
        assert result["passed"] is False, "NG-02 シートは不合格であるべきです"

    def test_ng02_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-02"][0]
        assert result["violation_count"] >= 1

    def test_ng02_violation_describes_duplicate_header(self, results_by_sheet):
        cr = results_by_sheet["NG-02"][0]["check_result"]
        assert any("重複" in v.description for v in cr.violations), "重複ヘッダーの違反メッセージが含まれていません"
        assert any("千円" in v.description for v in cr.violations), (
            "重複している項目名「千円」が違反メッセージに含まれていません"
        )


class TestNG03:
    """NG-03 シート: 単一行ヘッダーで横結合あり → L2 では結合ヘッダー自体を不許可

    構造:
      Row1: A="カテゴリ"(A1:B1 結合マスター), B=従属セル, C="値"
      Data: 行2以降

    L1-12 ではヘッダー結合は許容（info Violation）だが、
    L2-03 では結合ヘッダー自体を許容しない（除外パターンなし）。
    B 列が結合の従属セルとして違反になる。
    """

    def test_ng03_fails(self, results_by_sheet):
        assert "NG-03" in results_by_sheet, "NG-03 シートの結果が見つかりません"
        result = results_by_sheet["NG-03"][0]
        assert result["passed"] is False, "NG-03 シートは不合格であるべきです"

    def test_ng03_has_violations(self, results_by_sheet):
        result = results_by_sheet["NG-03"][0]
        assert result["violation_count"] >= 1

    def test_ng03_violation_describes_merged_header(self, results_by_sheet):
        cr = results_by_sheet["NG-03"][0]["check_result"]
        assert any("結合ヘッダー" in v.description for v in cr.violations), (
            "単一行結合ヘッダーの違反メッセージが含まれていません"
        )

    def test_ng03_violation_cell_range_points_to_full_merge(self, results_by_sheet):
        """違反箇所は親結合範囲全体（A1:B1）であり、従属セル単独ではない。"""
        cr = results_by_sheet["NG-03"][0]["check_result"]
        merge_violations = [v for v in cr.violations if "結合ヘッダー" in v.description]
        assert len(merge_violations) == 1
        # NG-03: 横結合 A1:B1（カテゴリ列）
        assert merge_violations[0].cell_range == "A1:B1"


class TestNG04:
    """NG-04 シート: 親行に複数の横結合グループ → 複数の違反

    構造:
      Row1: A=空, B="売上"(B1:C1 結合マスター), C=従属セル, D="経費"(D1:E1 結合マスター), E=従属セル
      Row2: A="会社", B="国内", C="海外", D="国内", E="海外"
      Data: 行3以降

    親行に 2 つの横結合グループ → C 列と E 列がそれぞれ従属セルとして違反。
    """

    def test_ng04_fails(self, results_by_sheet):
        assert "NG-04" in results_by_sheet, "NG-04 シートの結果が見つかりません"
        result = results_by_sheet["NG-04"][0]
        assert result["passed"] is False, "NG-04 シートは不合格であるべきです"

    def test_ng04_has_multiple_violations(self, results_by_sheet):
        cr = results_by_sheet["NG-04"][0]["check_result"]
        merge_violations = [v for v in cr.violations if "結合ヘッダー" in v.description]
        # B1:C1（売上）と D1:E1（経費）の親結合範囲 → 2 件以上
        assert len(merge_violations) >= 2, (
            f"複数の結合ヘッダー違反が期待されますが {len(merge_violations)} 件しか検出されませんでした"
        )

    def test_ng04_violations_cell_range_point_to_full_merges(self, results_by_sheet):
        """違反箇所は各親結合範囲（B1:C1 と D1:E1）であり、従属セル単独ではない。"""
        cr = results_by_sheet["NG-04"][0]["check_result"]
        merge_violations = [v for v in cr.violations if "結合ヘッダー" in v.description]
        cell_ranges = sorted(v.cell_range for v in merge_violations)
        # NG-04: B1:C1（売上）と D1:E1（経費）の 2 つの親結合範囲
        assert cell_ranges == ["B1:C1", "D1:E1"]
