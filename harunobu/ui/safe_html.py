"""HTML rendering helpers for Streamlit UI."""

from __future__ import annotations

from html import escape as _escape


def escape_html(value: object) -> str:
    """HTML text/attribute contexts 用に値をエスケープする。"""
    if value is None:
        return ""
    return _escape(str(value), quote=True)
