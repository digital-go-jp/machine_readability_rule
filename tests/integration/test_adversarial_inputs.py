"""異常系（いじわる）入力の例外契約テスト（CI ゲート・決定論）。"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harunobu.core.analyzer import Analyzer, analyze
from harunobu.core.reader import CorruptedFileError, UnsupportedFormatError, read_file, read_workbook

_APP_DIR = Path(__file__).resolve().parents[2]

# PNG マジックバイト（拡張子偽装テスト用）
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _cli(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """``python -m harunobu`` をサブプロセス実行する。"""
    return subprocess.run(
        [sys.executable, "-m", "harunobu", *args],
        cwd=str(_APP_DIR),
        capture_output=True,
        text=True,
        env={**os.environ, "HARUNOBU_AI_DISABLED": "true"},
        timeout=timeout,
    )


class TestCliMischief:
    """CLI（argparse / ``cmd_analyze``）の異常系。"""

    def test_no_subcommand_prints_help_and_exits_1(self) -> None:
        """サブコマンド無しはヘルプ表示して終了コード 1。"""
        proc = _cli()
        assert proc.returncode == 1
        assert "harunobu" in (proc.stdout + proc.stderr)

    def test_analyze_missing_file_arg_exits_2(self) -> None:
        """file 引数欠落は argparse エラー（終了コード 2）。"""
        assert _cli("analyze").returncode == 2

    def test_analyze_bogus_mode_exits_2(self) -> None:
        """未知の --mode は argparse の choices エラー（終了コード 2）。"""
        assert _cli("analyze", "dummy.xlsx", "--mode", "bogus").returncode == 2

    def test_analyze_bogus_output_exits_2(self) -> None:
        """未知の --output は argparse の choices エラー（終了コード 2）。"""
        assert _cli("analyze", "dummy.xlsx", "--output", "bogus").returncode == 2

    def test_analyze_nonexistent_file_exits_nonzero(self, tmp_path: Path) -> None:
        """存在しないファイルは非ゼロ終了（未捕捉の FileNotFoundError）。"""
        proc = _cli("analyze", str(tmp_path / "no_such.xlsx"))
        assert proc.returncode != 0

    def test_analyze_empty_xlsx_exits_nonzero(self, tmp_path: Path) -> None:
        """空の .xlsx は非ゼロ終了。"""
        empty = tmp_path / "empty.xlsx"
        empty.write_bytes(b"")
        assert _cli("analyze", str(empty)).returncode != 0


class TestSdkReaderMischief:
    """リーダー（``read_file`` / ``read_workbook``）の例外契約。"""

    def test_nonexistent_path_raises_file_not_found(self, tmp_path: Path) -> None:
        """存在しないパスは FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            read_file(tmp_path / "missing.xlsx")

    def test_xls_raises_unsupported(self, tmp_path: Path) -> None:
        """.xls は UnsupportedFormatError（内容を読む前に拒否）。"""
        xls = tmp_path / "legacy.xls"
        xls.write_bytes(b"anything")
        with pytest.raises(UnsupportedFormatError):
            read_file(xls)

    def test_unsupported_suffix_raises(self, tmp_path: Path) -> None:
        """未対応拡張子（.txt）は UnsupportedFormatError。"""
        txt = tmp_path / "data.txt"
        txt.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        with pytest.raises(UnsupportedFormatError):
            read_file(txt)

    def test_empty_xlsx_raises(self, tmp_path: Path) -> None:
        """空の .xlsx は UnsupportedFormatError か CorruptedFileError。"""
        empty = tmp_path / "empty.xlsx"
        empty.write_bytes(b"")
        with pytest.raises((UnsupportedFormatError, CorruptedFileError)):
            read_file(empty)

    def test_extension_spoofing_raises(self, tmp_path: Path) -> None:
        """中身が PNG の偽装 .xlsx は拒否される（Magika 有無どちらでも）。"""
        fake = tmp_path / "fake.xlsx"
        fake.write_bytes(_PNG_MAGIC + b"\x00" * 64)
        with pytest.raises((UnsupportedFormatError, CorruptedFileError)):
            read_file(fake)

    def test_corrupt_zip_bytes_raises_corrupted(self) -> None:
        """壊れた zip バイト列の .xlsx は CorruptedFileError か UnsupportedFormatError。"""
        with pytest.raises((CorruptedFileError, UnsupportedFormatError)):
            read_workbook("broken.xlsx", io.BytesIO(b"PK\x03\x04broken-zip-content"))

    def test_empty_bytes_stream_raises(self) -> None:
        """空バイトストリームの .xlsx は拒否される。"""
        with pytest.raises((CorruptedFileError, UnsupportedFormatError)):
            Analyzer(mode="standard").analyze_file("empty.xlsx", io.BytesIO(b""))


class TestSdkApiMischief:
    """SDK 公開 API の異常系。"""

    def test_analyze_wrong_type_raises(self) -> None:
        """数値を渡すと Path 変換で TypeError。"""
        with pytest.raises(TypeError):
            analyze(123)  # type: ignore[arg-type]

    def test_analyze_bulk_empty_list_is_handled(self) -> None:
        """空リストの一括分析は例外を投げず 0 件結果を返す。"""
        result = Analyzer(mode="standard").analyze_bulk([])
        assert result.file_count == 0

    def test_pathological_workbooks_do_not_crash(self, create_workbook) -> None:
        """空シート・単一セル・全結合などの病的入力でも採点が完走する。"""
        analyzer = Analyzer(mode="standard")
        cases = [
            create_workbook(sheets_data={"Sheet1": []}),
            create_workbook(sheets_data={"Sheet1": [["x"]]}),
            create_workbook(
                sheets_data={"Sheet1": [["a", "b"], ["1", "2"]]},
                merged_cells=[{"sheet": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 2, "end_col": 2}],
            ),
        ]
        for workbook in cases:
            result = analyzer.analyze(workbook)
            assert result.sheets  # SheetResult が返る（クラッシュしない）

    def test_reentrancy_same_analyzer_is_stable(self, create_workbook) -> None:
        """同一 Analyzer インスタンスを使い回しても結果が安定する（状態漏れ無し）。"""
        analyzer = Analyzer(mode="standard")
        workbook = create_workbook(sheets_data={"Sheet1": [["名前", "年齢"], ["太郎", 20], ["花子", 25]]})
        first = analyzer.analyze(workbook)
        second = analyzer.analyze(workbook)
        third = analyzer.analyze(workbook)
        rule_ids_first = sorted(first.sheets[0].tables[0].mr_result.all_results())
        rule_ids_third = sorted(third.sheets[0].tables[0].mr_result.all_results())
        assert rule_ids_first == rule_ids_third
        assert len(second.sheets) == len(first.sheets)
