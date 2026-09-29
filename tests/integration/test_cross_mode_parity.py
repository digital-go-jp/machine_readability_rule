"""モード横断パリティの回帰テスト（CI ゲート・決定論）。

検証する不変条件:
    1. CLI 出力 == SDK(CLI 内部経路) 出力（``HARUNOBU_AI_DISABLED=true`` 前提）。
       CLI は ``analyze(path, Config(mode))`` を呼ぶだけなので一致すべき。差分は実バグ。
    2. ``Analyzer(mode)`` が lite/standard/thorough で ``{1}/{1,2}/{1,2,3}`` を評価する。

なお、CLI の ``--mode`` が ``mr_levels`` を導出しなかった不具合（以前は ``analyze()`` に
``Config(mode=...)`` を渡すと既定 ``{1,2}`` のままだった）は修正済み
（``Config`` の ``_derive_mr_levels_from_mode`` validator）。その回帰テストは
``test_mode_parity.py`` にある。本ファイルはそれと相補的に、CLI サブプロセス・
Streamlit アップロード経路を含めたモード横断パリティを固定する。

"""

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harunobu.core.analyzer import Analyzer, analyze
from harunobu.core.models import Config
from harunobu.core.reader import read_file
from harunobu.output.json_writer import to_dict

_APP_DIR = Path(__file__).resolve().parents[2]
_SAMPLES_DIR = _APP_DIR / "tests" / "sample_by_mr_rules" / "samples"

# パリティ検証に用いる代表サンプル（xlsx の違反あり / OK な CSV）
_PARITY_SAMPLES = ["rule_12_merged_cells.xlsx", "rule_06_space_formatting_OK.csv"]
_MODES = ["lite", "standard", "thorough"]


@pytest.fixture(autouse=True)
def _disable_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI 補完を無効化し、採点を決定論にする（シングルトンもリセット）。"""
    monkeypatch.setenv("HARUNOBU_AI_DISABLED", "true")
    try:
        from harunobu.core.ai_visual_analyzer import AIVisualAnalyzer

        AIVisualAnalyzer.reset_instance()
    except Exception:  # noqa: BLE001 — リセット手段が無くても無効化は env で担保
        pass


def _canon(result: dict[str, Any]) -> dict[str, Any]:
    """採点結果辞書を比較可能な正規形にする（並列実行の順序揺れを吸収）。"""
    out = copy.deepcopy(result)
    for level_value in out.get("レベル別スコア", {}).values():
        if isinstance(level_value, dict):
            for key in ("失敗ルール", "強制0点ルール"):
                level_value[key] = sorted(
                    level_value.get(key, []),
                    key=lambda r: (str(r.get("ルールID", "")), str(r.get("重大度", ""))),
                )
    for sheet in out.get("sheets", []):
        for table in sheet.get("評価対象エリア", []):
            if "信頼度" in table:
                table["信頼度"] = round(table["信頼度"], 6)
            for check in table.get("評価内容", []):
                if "信頼度" in check:
                    check["信頼度"] = round(check["信頼度"], 6)
                check["違反"] = sorted(
                    check.get("違反", []),
                    key=lambda v: (
                        str(v.get("シート", "")),
                        str(v.get("セル範囲", "")),
                        str(v.get("説明", "")),
                        str(v.get("違反重大度", "")),
                    ),
                )
            table["評価内容"] = sorted(table.get("評価内容", []), key=lambda c: str(c.get("ルールID", "")))
    return out


def _evaluated_levels(result: dict[str, Any]) -> set[int]:
    """採点済み（null でない）レベル集合を返す。"""
    return {int(level) for level, value in result["レベル別スコア"].items() if value is not None}


def _run_cli_json(file: Path, mode: str) -> dict[str, Any]:
    """CLI（``python -m harunobu analyze``）を実行し JSON をパースして返す。"""
    proc = subprocess.run(
        [sys.executable, "-m", "harunobu", "analyze", str(file), "--mode", mode, "--output", "json"],
        cwd=str(_APP_DIR),
        capture_output=True,
        text=True,
        env={**os.environ, "HARUNOBU_AI_DISABLED": "true"},
        timeout=120,
    )
    assert proc.returncode == 0, f"CLI 異常終了 (mode={mode}): {proc.stderr[-500:]}"
    return json.loads(proc.stdout)


@pytest.mark.parametrize("sample", _PARITY_SAMPLES)
@pytest.mark.parametrize("mode", _MODES)
def test_cli_matches_sdk_cli_path(sample: str, mode: str) -> None:
    """CLI 出力と ``analyze(path, Config(mode))`` 出力が一致する。"""
    file = _SAMPLES_DIR / sample
    if not file.exists():
        pytest.skip(f"サンプル未生成: {sample}")

    cli_dict = _run_cli_json(file, mode)
    sdk_dict = to_dict(analyze(file, Config(mode=mode)))  # type: ignore[arg-type]
    assert _canon(cli_dict) == _canon(sdk_dict)


@pytest.mark.parametrize(
    ("mode", "expected_levels"),
    [("lite", {1}), ("standard", {1, 2}), ("thorough", {1, 2, 3})],
)
def test_analyzer_evaluates_correct_levels(mode: str, expected_levels: set[int]) -> None:
    """``Analyzer(mode)`` がモードに対応するレベルだけを評価する。"""
    file = _SAMPLES_DIR / "rule_12_merged_cells.xlsx"
    if not file.exists():
        pytest.skip("サンプル未生成: rule_12_merged_cells.xlsx")

    result = Analyzer(mode=mode).analyze(read_file(file))
    assert _evaluated_levels(to_dict(result)) == expected_levels


@pytest.mark.parametrize("sample", _PARITY_SAMPLES)
def test_streamlit_path_matches_file_path(sample: str) -> None:
    """Streamlit のアップロード経路 (``analyze_file``) がファイル経路と同じ採点になる（S0）。

    Streamlit ページは ``Analyzer(mode).analyze_file(name, bytes)`` を呼ぶ。これが
    ``Analyzer(mode).analyze(read_file(path))`` と同じ採点（sheets / レベル別スコア）を
    返すことを確認し、UI 計算経路の整合性を担保する。
    """
    file = _SAMPLES_DIR / sample
    if not file.exists():
        pytest.skip(f"サンプル未生成: {sample}")

    via_path = to_dict(Analyzer(mode="standard").analyze(read_file(file)))
    via_stream = to_dict(Analyzer(mode="standard").analyze_file(file.name, io.BytesIO(file.read_bytes())))
    for key in ("sheets", "レベル別スコア"):
        assert _canon(via_path)[key] == _canon(via_stream)[key]
