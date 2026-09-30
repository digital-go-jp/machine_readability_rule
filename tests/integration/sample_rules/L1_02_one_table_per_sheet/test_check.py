"""L1-02: 1シート1表チェック — sample_by_mr_rules サンプルによる検証

サンプル:
  - rule_02_multiple_tables.xlsx       → シート「OK」は pass、シート「NG-01」は fail
  - rule_02_multiple_tables_NG-01.csv  → 複数テーブルが含まれるので NG
  - rule_02_multiple_tables_OK.csv     → 1テーブルのみなので OK
"""

from __future__ import annotations

import pytest

from tests.integration.sample_rules.conftest import (
    analyze_file,
    collect_samples,
    get_rule_result,
    get_rule_results_by_sheet,
    is_ok_sample,
)

RULE_NUMBER = 2
RULE_ID = "L1-02"


@pytest.fixture(scope="module")
def sample_files(samples_dir):
    """L1-02 用サンプルを収集する。"""
    files = collect_samples(RULE_NUMBER, samples_dir)
    if not files:
        pytest.skip(f"rule_{RULE_NUMBER:02d}_* のサンプルが見つかりません")
    return files


@pytest.fixture(scope="module")
def ok_csv_files(sample_files):
    return [f for f in sample_files if is_ok_sample(f)]


@pytest.fixture(scope="module")
def ng_csv_files(sample_files):
    """NG の CSV ファイル（ファイル名に NG を含む単一シートファイル）。"""
    return [f for f in sample_files if not is_ok_sample(f) and f.suffix == ".csv"]


@pytest.fixture(scope="module")
def xlsx_files(sample_files):
    """複数シート（OK/NG）を含む xlsx ファイル。"""
    return [f for f in sample_files if f.suffix == ".xlsx"]


class TestL1_02_OK_CSV:
    """OK CSV サンプル: 1シート1表のファイルは L1-02 に合格する。"""

    def test_ok_samples_exist(self, ok_csv_files):
        assert len(ok_csv_files) > 0, "OK CSVサンプルが1つ以上必要"

    def test_ok_files_pass(self, ok_csv_files):
        for path in ok_csv_files:
            result = analyze_file(path)
            rule_result = get_rule_result(result, RULE_ID)
            assert rule_result["found"], f"{path.name}: L1-02 の結果が見つかりません"
            assert rule_result["passed"], (
                f"{path.name}: OK サンプルなのに L1-02 に不合格 "
                f"(severity={rule_result['severity']}, violations={rule_result['violation_count']})"
            )


class TestL1_02_NG_CSV:
    """NG CSV サンプル: 複数テーブルを含む CSV は L1-02 に不合格になる。"""

    def test_ng_samples_exist(self, ng_csv_files):
        assert len(ng_csv_files) > 0, "NG CSVサンプルが1つ以上必要"

    def test_ng_files_fail(self, ng_csv_files):
        for path in ng_csv_files:
            result = analyze_file(path)
            rule_result = get_rule_result(result, RULE_ID)
            assert rule_result["found"], f"{path.name}: L1-02 の結果が見つかりません"
            assert not rule_result["passed"], (
                f"{path.name}: NG サンプルなのに L1-02 に合格 "
                f"(severity={rule_result['severity']}, violations={rule_result['violation_count']})"
            )


class TestL1_02_XLSX:
    """xlsx サンプル: シート名 OK は合格、NG-* は不合格。"""

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
            for sheet_name, results in ng_sheets.items():
                has_failure = any(not r["passed"] for r in results)
                assert has_failure, f"{path.name} sheet={sheet_name}: NG シートなのに全テーブル合格"
