"""L1-05: 列ヘッダーチェック — sample_by_mr_rules サンプルによる検証

サンプル:
  - rule_05_missing_column_names.xlsx → シート「OK」は pass、シート「NG-*」は fail を期待
    ※ NG-02 は現状 pass（AI補完なしでは検出困難なケースの可能性）
"""

from __future__ import annotations

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    collect_samples,
    get_rule_results_by_sheet,
    is_ok_sample,
)

RULE_NUMBER = 5
RULE_ID = "L1-05"


@pytest.fixture(scope="module")
def sample_files(samples_dir):
    """L1-05 用サンプルを収集する。"""
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


class TestL1_05_XLSX:
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
