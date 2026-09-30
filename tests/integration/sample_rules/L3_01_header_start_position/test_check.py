"""L3-01: ヘッダー開始位置チェック — sample_by_mr_rules サンプルによる検証

サンプル:
  - rule_22_header_start_position.xlsx
      OK: 1 行目ヘッダ → pass を期待
      NG-01: 先頭行にタイトル、ヘッダが下にずれる → fail を期待
      NG-02: ヘッダー行とデータ行の間に空白行 → fail を期待（レイアウト推定で
        テーブルが分割される場合でも、いずれかのテーブルで違反が出ることを確認）
      NG-03: 3 行多段ヘッダー → fail を期待（重大度は MAJOR）
  - rule_22_header_start_position_OK.csv → pass を期待
  - rule_22_header_start_position_NG-01.csv → fail を期待

L3 ルールは thorough モードでのみ実行されるため、本テストは独自に
Analyzer(mode="thorough") を構築する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harunobu.core.analyzer import Analyzer
from harunobu.core.models import AnalysisResult
from harunobu.core.reader import read_file
from harunobu.core.severity import Severity
from tests.integration.sample_rules.conftest import collect_samples, is_ok_sample

RULE_NUMBER = 22
RULE_ID = "L3-01"


def _analyze_thorough(path: Path) -> AnalysisResult:
    workbook = read_file(path)
    return Analyzer(mode="thorough").analyze(workbook)


def _results_by_sheet(analysis: AnalysisResult, rule_id: str) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {}
    for sheet_result in analysis.sheets:
        sheet_name = sheet_result.sheet_meta.name
        for table_result in sheet_result.tables:
            all_results = table_result.mr_result.all_results()
            if rule_id in all_results:
                cr = all_results[rule_id]
                results.setdefault(sheet_name, []).append(
                    {
                        "passed": cr.passed,
                        "severity": cr.effective_severity,
                        "violation_count": len(cr.violations),
                        "check_result": cr,
                    }
                )
    return results


@pytest.fixture(scope="module")
def sample_files(samples_dir):
    files = collect_samples(RULE_NUMBER, samples_dir)
    if not files:
        pytest.skip(f"rule_{RULE_NUMBER:02d}_* のサンプルが見つかりません")
    return files


@pytest.fixture(scope="module")
def xlsx_files(sample_files):
    return [f for f in sample_files if f.suffix == ".xlsx"]


@pytest.fixture(scope="module")
def csv_files(sample_files):
    return [f for f in sample_files if f.suffix == ".csv"]


class TestL3_01_XLSX:
    """xlsx サンプル: OK シートは合格、NG-* シートは違反を検出。"""

    def test_xlsx_samples_exist(self, xlsx_files):
        assert len(xlsx_files) > 0, "xlsx サンプルが 1 つ以上必要"

    def test_ok_sheets_pass(self, xlsx_files):
        for path in xlsx_files:
            analysis = _analyze_thorough(path)
            by_sheet = _results_by_sheet(analysis, RULE_ID)
            ok_sheets = {k: v for k, v in by_sheet.items() if k.startswith("OK")}
            assert ok_sheets, f"{path.name}: OK シートで L3-01 が実行されていません"
            for sheet_name, results in ok_sheets.items():
                for r in results:
                    assert r["passed"], (
                        f"{path.name} sheet={sheet_name}: OK シートなのに不合格 "
                        f"(severity={r['severity'].value}, violations={r['violation_count']})"
                    )

    def test_ng_sheets_fail(self, xlsx_files):
        for path in xlsx_files:
            analysis = _analyze_thorough(path)
            by_sheet = _results_by_sheet(analysis, RULE_ID)
            ng_sheets = {k: v for k, v in by_sheet.items() if k.startswith("NG")}
            assert ng_sheets, f"{path.name}: NG シートが見つかりません"
            not_detected: list[str] = []
            for sheet_name, results in ng_sheets.items():
                has_failure = any(not r["passed"] for r in results)
                if not has_failure:
                    not_detected.append(sheet_name)
            if not_detected:
                pytest.fail(
                    f"{path.name}: 以下の NG シートで {RULE_ID} 違反を検出できませんでした:\n"
                    + "\n".join(f"  - {s}" for s in not_detected)
                )

    def test_ng_01_is_fatal(self, xlsx_files):
        """NG-01（タイトル行先行）は FATAL severity を返す。"""
        for path in xlsx_files:
            analysis = _analyze_thorough(path)
            by_sheet = _results_by_sheet(analysis, RULE_ID)
            results = by_sheet.get("NG-01", [])
            failed = [r for r in results if not r["passed"]]
            assert failed, f"{path.name}: NG-01 で L3-01 違反が検出されません"
            assert any(r["severity"] == Severity.FATAL for r in failed), (
                f"{path.name}: NG-01 の L3-01 違反は FATAL であるべき (actual={[r['severity'].value for r in failed]})"
            )

    def test_ng_03_is_major(self, xlsx_files):
        """NG-03（3 行多段ヘッダーのみ）は MAJOR severity（強制 0 点ではない）。"""
        for path in xlsx_files:
            analysis = _analyze_thorough(path)
            by_sheet = _results_by_sheet(analysis, RULE_ID)
            results = by_sheet.get("NG-03", [])
            failed = [r for r in results if not r["passed"]]
            assert failed, f"{path.name}: NG-03 で L3-01 違反が検出されません"
            assert all(r["severity"] == Severity.MAJOR for r in failed), (
                f"{path.name}: NG-03 の L3-01 違反は MAJOR であるべき (actual={[r['severity'].value for r in failed]})"
            )


class TestL3_01_CSV:
    """CSV サンプル: OK は合格、NG-* は違反を検出。"""

    def test_csv_samples_exist(self, csv_files):
        assert len(csv_files) > 0, "csv サンプルが 1 つ以上必要"

    def test_ok_csv_passes(self, csv_files):
        ok_paths = [p for p in csv_files if is_ok_sample(p)]
        assert ok_paths, "OK の csv サンプルが必要"
        for path in ok_paths:
            analysis = _analyze_thorough(path)
            by_sheet = _results_by_sheet(analysis, RULE_ID)
            assert by_sheet, f"{path.name}: L3-01 が実行されていません"
            for sheet_name, results in by_sheet.items():
                for r in results:
                    assert r["passed"], (
                        f"{path.name} sheet={sheet_name}: OK csv なのに不合格 "
                        f"(severity={r['severity'].value}, violations={r['violation_count']})"
                    )

    def test_ng_csv_fails(self, csv_files):
        ng_paths = [p for p in csv_files if not is_ok_sample(p)]
        assert ng_paths, "NG の csv サンプルが必要"
        for path in ng_paths:
            analysis = _analyze_thorough(path)
            by_sheet = _results_by_sheet(analysis, RULE_ID)
            assert by_sheet, f"{path.name}: L3-01 が実行されていません"
            any_failure = any(not r["passed"] for results in by_sheet.values() for r in results)
            assert any_failure, f"{path.name}: NG csv なのに L3-01 違反が検出されません"
