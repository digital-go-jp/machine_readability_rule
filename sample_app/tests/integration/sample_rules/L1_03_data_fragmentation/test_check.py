"""L1-03: データ分断チェック — sample_by_mr_rules サンプルによる検証

サンプル:
  - rule_03_fragmented_data.xlsx → シート「OK」は pass、シート「NG-*」は fail を期待
    - レイアウト推定の gap_threshold で 2 行以上の空行による分割が発生する場合も、
      L1-03 はシート内のテーブル間空白行を検出して違反として報告する。
"""

from __future__ import annotations

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    collect_samples,
    get_rule_results_by_sheet,
    is_ok_sample,
)

RULE_NUMBER = 3
RULE_ID = "L1-03"


@pytest.fixture(scope="module")
def sample_files(samples_dir):
    """L1-03 用サンプルを収集する。"""
    files = collect_samples(RULE_NUMBER, samples_dir)
    if not files:
        pytest.skip(f"rule_{RULE_NUMBER:02d}_* のサンプルが見つかりません")
    return files


@pytest.fixture(scope="module")
def xlsx_files(sample_files):
    return [f for f in sample_files if f.suffix == ".xlsx"]


@pytest.fixture(scope="module")
def csv_ok_files(sample_files):
    return [f for f in sample_files if f.suffix == ".csv" and is_ok_sample(f)]


@pytest.fixture(scope="module")
def csv_ng_files(sample_files):
    return [f for f in sample_files if f.suffix == ".csv" and not is_ok_sample(f)]


class TestL1_03_XLSX:
    """xlsx サンプル: シート名 OK は合格、NG-* シートは個別に検証。"""

    def test_xlsx_samples_exist(self, xlsx_files):
        assert len(xlsx_files) > 0, "xlsxサンプルが1つ以上必要"

    def test_ok_sheets_pass(self, xlsx_files):
        for path in xlsx_files:
            result = analyze_file(path)
            by_sheet = get_rule_results_by_sheet(result, RULE_ID)
            ok_sheets = {k: v for k, v in by_sheet.items() if k.startswith("OK")}
            for sheet_name, results in ok_sheets.items():
                for r in results:
                    assert r["passed"], (
                        f"{path.name} sheet={sheet_name}: OK シートなのに不合格 "
                        f"(score={r['score']}, violations={r['violation_count']})"
                    )

    def test_ng_sheets_fail(self, xlsx_files):
        for path in xlsx_files:
            result = analyze_file(path)
            by_sheet = get_rule_results_by_sheet(result, RULE_ID)
            ng_sheets = {k: v for k, v in by_sheet.items() if k.startswith("NG")}
            assert len(ng_sheets) > 0, f"{path.name}: NGシートが見つかりません"
            not_detected: list[str] = []
            for sheet_name, results in ng_sheets.items():
                has_failure = any(not r["passed"] for r in results)
                if not has_failure:
                    scores = [(r["score"], r["violation_count"]) for r in results]
                    not_detected.append(f"{sheet_name} (scores={scores})")
            if not_detected:
                pytest.fail(
                    f"{path.name}: 以下の NG シートで {RULE_ID} 違反を検出できませんでした:\n"
                    + "\n".join(f"  - {s}" for s in not_detected)
                )
