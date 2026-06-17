"""sample_by_mr_rules サンプルを使ったルール検証テスト共通fixture"""

from __future__ import annotations

from pathlib import Path

import pytest

from harunobu.core.analyzer import Analyzer
from harunobu.core.models import AnalysisResult
from harunobu.core.reader import read_file

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "sample_by_mr_rules" / "samples"


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """サンプルファイルのディレクトリを返す。存在しなければスキップ。"""
    if not SAMPLES_DIR.exists():
        pytest.skip(f"サンプルディレクトリが見つかりません: {SAMPLES_DIR}")
    return SAMPLES_DIR


def collect_samples(rule_number: int, samples_dir: Path) -> list[Path]:
    """ルール番号に対応するサンプルファイルを収集する。"""
    prefix = f"rule_{rule_number:02d}_"
    files = sorted(p for p in samples_dir.iterdir() if p.is_file() and p.name.startswith(prefix))
    return files


def is_ok_sample(path: Path) -> bool:
    """ファイル名から OK サンプルかどうかを判定する。"""
    stem = path.stem
    return "_OK" in stem


def analyze_file(path: Path) -> AnalysisResult:
    """ファイルを読み込み、standard モードで分析して結果を返す。"""
    workbook = read_file(path)
    analyzer = Analyzer(mode="standard")
    return analyzer.analyze(workbook)


def get_rule_result(analysis: AnalysisResult, rule_id: str) -> dict:
    """AnalysisResult から特定ルールの CheckResult を探す。

    Returns:
        dict: {"passed": bool, "score": int, "violation_count": int, "check_result": CheckResult}
            ルールが見つからなかった場合は {"found": False}
    """
    for sheet_result in analysis.sheets:
        for table_result in sheet_result.tables:
            all_results = table_result.mr_result.all_results()
            if rule_id in all_results:
                cr = all_results[rule_id]
                return {
                    "found": True,
                    "passed": cr.passed,
                    "severity": cr.effective_severity.value,
                    "violation_count": len(cr.violations),
                    "check_result": cr,
                }
    return {"found": False}


def get_rule_results_by_sheet(analysis: AnalysisResult, rule_id: str) -> dict[str, list[dict]]:
    """AnalysisResult からシート名をキーにして特定ルールの CheckResult を返す。

    Returns:
        dict[str, list[dict]]: シート名をキーにして、各シートでの判定結果リストを返す。
            各要素は {"passed": bool, "score": int, "violation_count": int, "check_result": CheckResult} の dict。
    """
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
                        "severity": cr.effective_severity.value,
                        "violation_count": len(cr.violations),
                        "check_result": cr,
                    }
                )
    return results
