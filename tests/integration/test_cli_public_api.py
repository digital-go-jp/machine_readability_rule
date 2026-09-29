"""公開CLIとトップレベルSDK APIの回帰テスト。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harunobu.__main__ import main

_SAMPLE = Path(__file__).parent.parent / "sample_by_mr_rules" / "samples" / "rule_12_merged_cells.xlsx"


def _run_cli(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["harunobu", *argv])
    main()


def test_root_help_does_not_show_metrics(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["harunobu", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Excel/CSV/TSVを機械可読性ルールで判定するCLI" in output
    assert "analyze" in output
    assert "metrics" not in output


def test_metrics_command_is_not_available(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["harunobu", "metrics"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    output = capsys.readouterr()
    assert "invalid choice" in output.err
    assert "metrics" in output.err


def test_analyze_help_is_japanese_and_has_examples(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["harunobu", "analyze", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Excel/CSV/TSVファイルを読み込み" in output
    assert "判定モード" in output
    assert "出力形式" in output
    assert "例:" in output
    assert "uv run harunobu analyze data.xlsx" in output


def test_analyze_outputs_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _run_cli(monkeypatch, ["analyze", str(_SAMPLE), "--output", "json"])

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["inputファイル名"] == _SAMPLE.name
    assert parsed["フォーマット"] == "xlsx"
    assert "レベル別スコア" in parsed
    assert "sheets" in parsed


def test_analyze_excludes_original_description_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli(monkeypatch, ["analyze", str(_SAMPLE), "--output", "json"])

    parsed = json.loads(capsys.readouterr().out)
    check = parsed["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
    assert "原本説明" not in check


def test_analyze_with_original_description_flag_includes_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_cli(monkeypatch, ["analyze", str(_SAMPLE), "--output", "json", "--with-original-description"])

    parsed = json.loads(capsys.readouterr().out)
    check = parsed["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
    assert "原本説明" in check
    assert check["原本説明"]


def test_top_level_sdk_exports() -> None:
    from harunobu import AnalysisResult, Config, analyze

    result = analyze(_SAMPLE, Config(mode="lite"))

    assert isinstance(result, AnalysisResult)
    assert result.file_meta.name == _SAMPLE.name
