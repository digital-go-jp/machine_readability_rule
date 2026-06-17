"""マルチヘッダー時のセル結合に対する L1-05 / L1-12 / L2-03 の整合性テスト

ポリシー:
- L1 では許す（L1-05 = pass, L1-12 = pass）
- L2 では許さない（L2-03 = fail）

サンプル: rule_18_unique_column.xlsx

  NG-03 — 単一行ヘッダーで A-B 列に横結合（カテゴリ列）
  NG-04 — 親行に複数の横結合グループ（売上=B-C, 経費=D-E）
"""

from __future__ import annotations

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    get_rule_results_by_sheet,
)

SAMPLE_STEM = "rule_18_unique_column"


@pytest.fixture(scope="module")
def sample_path(samples_dir):
    path = samples_dir / f"{SAMPLE_STEM}.xlsx"
    if not path.exists():
        pytest.skip(f"サンプルが見つかりません: {path}")
    return path


@pytest.fixture(scope="module")
def analysis(sample_path):
    return analyze_file(sample_path)


def _get_sheet_result(analysis, rule_id: str, sheet: str) -> dict | None:
    by_sheet = get_rule_results_by_sheet(analysis, rule_id)
    if sheet not in by_sheet:
        return None
    return by_sheet[sheet][0]


class TestNG03Consistency:
    """NG-03（単一行ヘッダー + 横結合）: L1 では許す / L2 では許さない"""

    def test_l1_05_passes(self, analysis):
        """L1-05: ヘッダー結合は展開してヘッダー有りとみなす → pass"""
        result = _get_sheet_result(analysis, "L1-05", "NG-03")
        assert result is not None, "L1-05 の結果が見つかりません"
        assert result["passed"] is True, "L1-05 はヘッダー結合があっても pass であるべきです"

    def test_l1_12_passes(self, analysis):
        """L1-12: ヘッダー領域の結合のみ → pass（info Violation）"""
        result = _get_sheet_result(analysis, "L1-12", "NG-03")
        assert result is not None, "L1-12 の結果が見つかりません"
        assert result["passed"] is True, "L1-12 はヘッダー結合のみなら pass であるべきです"

    def test_l2_03_fails(self, analysis):
        """L2-03: 結合ヘッダーを許容しない → fail"""
        result = _get_sheet_result(analysis, "L2-03", "NG-03")
        assert result is not None, "L2-03 の結果が見つかりません"
        assert result["passed"] is False, "L2-03 は結合ヘッダーを違反として検出すべきです"


class TestNG04Consistency:
    """NG-04（複数のマルチヘッダー + セル結合）: L1 では許す / L2 では許さない"""

    def test_l1_05_passes(self, analysis):
        """L1-05: 親行の複数横結合をそれぞれ展開して pass"""
        result = _get_sheet_result(analysis, "L1-05", "NG-04")
        assert result is not None, "L1-05 の結果が見つかりません"
        assert result["passed"] is True, "L1-05 は複数のヘッダー結合があっても pass であるべきです"

    def test_l1_12_passes(self, analysis):
        """L1-12: 複数のヘッダー結合のみ（データ領域結合なし）→ pass"""
        result = _get_sheet_result(analysis, "L1-12", "NG-04")
        assert result is not None, "L1-12 の結果が見つかりません"
        assert result["passed"] is True, "L1-12 は複数のヘッダー結合のみなら pass であるべきです"

    def test_l2_03_fails_with_multiple_violations(self, analysis):
        """L2-03: 各結合グループの従属セルがそれぞれ違反 → fail"""
        result = _get_sheet_result(analysis, "L2-03", "NG-04")
        assert result is not None, "L2-03 の結果が見つかりません"
        assert result["passed"] is False, "L2-03 は複数の結合ヘッダーを違反として検出すべきです"
        cr = result["check_result"]
        merge_violations = [v for v in cr.violations if "結合ヘッダー" in v.description]
        assert len(merge_violations) >= 2, (
            f"複数の結合ヘッダー違反が期待されますが {len(merge_violations)} 件しか検出されませんでした"
        )
