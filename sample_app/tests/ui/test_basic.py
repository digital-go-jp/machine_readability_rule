"""Playwright E2E テスト: 基本的な UI フロー

Streamlit アプリを起動し、ファイルアップロード → プレビュー遷移を検証する。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Playwright / Streamlit が利用できない場合は E2E だけスキップ
playwright_available = importlib.util.find_spec("playwright") is not None
streamlit_available = importlib.util.find_spec("streamlit") is not None

e2e_skip = pytest.mark.skipif(
    not (playwright_available and streamlit_available),
    reason="playwright or streamlit is not installed",
)

# テスト用 Excel ファイルのパス
_TEST_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class _FakeUploadFile:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def _load_upload_module(monkeypatch):
    fake_streamlit = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    sys.modules.pop("harunobu.ui.styles", None)
    sys.modules.pop("harunobu.ui.pages.upload", None)
    return importlib.import_module("harunobu.ui.pages.upload")


@pytest.fixture(scope="session", autouse=True)
def _create_test_excel() -> None:
    """テスト用の小さな Excel ファイルを作成する。"""
    _TEST_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    xlsx_path = _TEST_FIXTURES_DIR / "test_data.xlsx"
    if xlsx_path.exists():
        return

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["ID", "名前", "値"])
    ws.append([1, "テストA", 100])
    ws.append([2, "テストB", 200])
    wb.save(str(xlsx_path))


def test_upload_limit_constants_and_types(monkeypatch) -> None:
    upload = _load_upload_module(monkeypatch)

    assert upload.MAX_UPLOAD_FILES == 20
    assert upload.MAX_UPLOAD_MB == 10
    assert upload.MAX_TOTAL_UPLOAD_MB == 50
    assert upload._ALLOWED_UPLOAD_TYPES == ("xlsx", "csv", "tsv")


def test_upload_limit_errors_block_count_and_size(monkeypatch) -> None:
    upload = _load_upload_module(monkeypatch)

    too_many = [_FakeUploadFile(f"{i}.csv", b"a,b\n") for i in range(upload.MAX_UPLOAD_FILES + 1)]
    errors = upload._get_upload_limit_errors(too_many)
    assert any("最大 20 件" in error for error in errors)

    too_large = [_FakeUploadFile("large.xlsx", b"x" * (upload.MAX_UPLOAD_MB * upload._BYTES_PER_MB + 1))]
    errors = upload._get_upload_limit_errors(too_large)
    assert any("1ファイルあたりの上限は 10 MB" in error for error in errors)


def test_upload_limit_errors_block_total_size(monkeypatch) -> None:
    upload = _load_upload_module(monkeypatch)

    files = [
        _FakeUploadFile(f"{i}.csv", b"x" * (3 * upload._BYTES_PER_MB))
        for i in range((upload.MAX_TOTAL_UPLOAD_MB // 3) + 1)
    ]
    errors = upload._get_upload_limit_errors(files)

    assert any("アップロード全体の上限は 50 MB" in error for error in errors)


@e2e_skip
def test_upload_page_loads(streamlit_server: str, page) -> None:
    """アップロードページが正常にロードされることを確認する。"""
    page.goto(streamlit_server, wait_until="networkidle")

    # Streamlit の初期ロードを待つ
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=15000)

    # ヘッダーテキスト「ファイルアップロード」が表示される（メインコンテンツ内）
    header = page.locator(".page-header-title", has_text="ファイルアップロード")
    header.wait_for(timeout=10000)
    assert header.is_visible()


@e2e_skip
def test_file_uploader_visible(streamlit_server: str, page) -> None:
    """ファイルアップローダーが表示されていることを確認する。"""
    page.goto(streamlit_server, wait_until="networkidle")
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=15000)

    # file_uploader ウィジェットが存在する
    uploader = page.locator("[data-testid='stFileUploader']")
    uploader.wait_for(timeout=10000)
    assert uploader.is_visible()


@e2e_skip
def test_upload_and_transition_to_preview(streamlit_server: str, page) -> None:
    """Excel をアップロードし、PREVIEW ページへ遷移することを確認する。"""
    page.goto(streamlit_server, wait_until="networkidle")
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=15000)

    # ファイルアップローダーにテストファイルをセット
    xlsx_path = _TEST_FIXTURES_DIR / "test_data.xlsx"
    uploader_input = page.locator("[data-testid='stFileUploader'] input[type='file']")

    # Streamlit の file_uploader は hidden input を使う
    # set_input_files で直接ファイルを送る
    uploader_input.set_input_files(str(xlsx_path))

    # アップロード成功メッセージを待つ
    success_msg = page.locator("text=test_data.xlsx")
    success_msg.wait_for(timeout=10000)

    # 「次へ」ボタンをクリック
    next_button = page.locator("text=次へ: データプレビュー")
    next_button.wait_for(timeout=10000)
    next_button.click()

    # PREVIEW ページへの遷移を確認
    preview_header = page.locator(".page-header-title", has_text="データプレビュー")
    preview_header.wait_for(timeout=15000)
    assert preview_header.is_visible()
