"""Harunobu Streamlit メインアプリケーション

ページルーティングとセッション状態の初期化を行う。
"""

from __future__ import annotations

import streamlit as st

from harunobu.ui.components.sidebar import render_sidebar
from harunobu.ui.pages import preview, result, scoring, upload, validation
from harunobu.ui.styles import inject_custom_css

# ページ設定
st.set_page_config(
    page_title="機械可読性チェックツール",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="auto",
)

# セッション状態の初期化
_DEFAULT_SESSION: dict[str, object] = {
    "workflow_step": "UPLOAD",
    "_prev_workflow_step": None,
    "uploaded_file": None,
    "uploaded_files": [],
    "active_file_index": 0,
    "workbook": None,
    "analysis_result": None,
    "bulk_analysis_result": None,
}

for key, default in _DEFAULT_SESSION.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ページルーティング
_PAGE_RENDERERS: dict[str, object] = {
    "UPLOAD": upload.render,
    "PREVIEW": preview.render,
    "VALIDATION": validation.render,
    "SCORING": scoring.render,
    "RESULT": result.render,
}


def main() -> None:
    """メインアプリケーションを実行する。"""
    inject_custom_css()
    render_sidebar()

    current_step = st.session_state.get("workflow_step", "UPLOAD")

    if st.session_state.get("_prev_workflow_step") != current_step:
        scroll_script = """<script>
            var el = window.parent.document.querySelector('[data-testid="stMain"]');
            if (el) el.scrollTop = 0;
            </script>"""
        st.session_state._prev_workflow_step = current_step
    else:
        scroll_script = ""
    # 要素を常に同じ位置に配置することで、rerun をまたいだ要素位置のずれを防ぐ
    st.components.v1.html(scroll_script, height=0)

    renderer = _PAGE_RENDERERS.get(current_step)

    if renderer is not None:
        renderer()
    else:
        st.error(f"不明なワークフローステップ: {current_step}")
        st.session_state.workflow_step = "UPLOAD"
        st.rerun()


if __name__ == "__main__":
    main()
