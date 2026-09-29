"""UI テスト用 fixture

Streamlit サーバーの起動・停止を管理する。
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest

_APP_MODULE = str(Path(__file__).resolve().parents[2] / "harunobu" / "ui" / "app.py")
_STARTUP_TIMEOUT = 15  # seconds


def _find_free_port() -> int:
    """OS にランダムな空きポートを割り当ててもらう。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = _STARTUP_TIMEOUT) -> bool:
    """サーバーが応答するまで待機する。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="session")
def streamlit_server() -> Generator[str, None, None]:
    """Streamlit サーバーをサブプロセスで起動し、URL を返す。

    セッションスコープなので全 UI テストで共有される。
    """
    port = _find_free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            _APP_MODULE,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
            "--browser.gatherUsageStats",
            "false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = f"http://127.0.0.1:{port}"
    try:
        if not _wait_for_server(port):
            stdout = proc.stdout.read().decode() if proc.stdout else ""
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            pytest.fail(
                f"Streamlit server failed to start within {_STARTUP_TIMEOUT}s.\nstdout: {stdout}\nstderr: {stderr}"
            )
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
