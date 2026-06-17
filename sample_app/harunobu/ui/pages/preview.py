"""データプレビューページ"""

from __future__ import annotations

from io import BytesIO

import streamlit as st

from harunobu.core.models import WorkBook
from harunobu.ui.safe_html import escape_html
from harunobu.ui.styles import page_header


def render() -> None:
    """データプレビューページを描画する。"""
    page_header("👁", "データプレビュー", "アップロードされたファイルの内容を確認できます。")

    uploaded_file = st.session_state.get("uploaded_file")
    if uploaded_file is None:
        st.warning("ファイルがアップロードされていません。")
        if st.button("← アップロードに戻る"):
            st.session_state.workflow_step = "UPLOAD"
            st.rerun()
        return

    file_name: str = uploaded_file.name
    file_bytes: bytes = uploaded_file.getvalue()

    # WorkBook の読み込みを試みる
    workbook = _load_workbook(file_name, file_bytes)

    if workbook is not None:
        st.session_state.workbook = workbook
        _render_workbook_preview(workbook)
    else:
        _render_pandas_preview(file_name, file_bytes)

    # ナビゲーション
    st.markdown("---")
    col1, _, col2 = st.columns([1, 2, 1])
    with col1:
        if st.button("← アップロード", width="stretch"):
            st.session_state.workflow_step = "UPLOAD"
            st.rerun()
    with col2:
        if st.button("レイアウト検出 →", type="primary", width="stretch"):
            st.session_state.workflow_step = "VALIDATION"
            st.rerun()


def _load_workbook(file_name: str, file_bytes: bytes) -> WorkBook | None:
    """コアの Reader を使って WorkBook を読み込む。"""
    try:
        from harunobu.core.reader import read_workbook

        return read_workbook(file_name, BytesIO(file_bytes))
    except (ImportError, Exception):
        return None


def _render_workbook_preview(workbook: WorkBook) -> None:
    """WorkBook モデルからプレビューを表示する。"""
    # ファイル情報カード
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="info-card-label">ファイル名</div>'
            f'<div class="info-card-value info-card-value-compact break-all">'
            f"{escape_html(workbook.file_name)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="info-card-label">フォーマット</div>'
            f'<div class="info-card-value">{escape_html(workbook.file_format.upper())}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="info-card-label">シート数</div>'
            f'<div class="info-card-value">{len(workbook.sheets)}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    if not workbook.sheets:
        st.info("シートが見つかりませんでした。")
        return

    st.markdown("")  # spacer

    # シート選択
    sheet_names = [s.name for s in workbook.sheets]
    selected = st.selectbox("📋 シートを選択", sheet_names, label_visibility="visible")

    sheet = workbook.get_sheet(selected) if selected else workbook.sheets[0]
    if sheet is None:
        return

    # シートメタ情報
    meta_cols = st.columns(3)
    meta_cols[0].metric("行数", f"{sheet.max_row:,}")
    meta_cols[1].metric("列数", f"{sheet.max_col:,}")
    merged_count = len(sheet.merged_cells) if sheet.merged_cells else 0
    meta_cols[2].metric("結合セル", f"{merged_count:,} 箇所")

    # データテーブル
    try:
        import pandas as pd

        rows: list[dict[str, object]] = []
        max_preview_rows = min(sheet.max_row, 50)
        for r in range(1, max_preview_rows + 1):
            row_data: dict[str, object] = {}
            for c in range(1, sheet.max_col + 1):
                val = sheet.get_cell_value(r, c)
                row_data[f"列{c}"] = str(val) if val is not None else ""
            rows.append(row_data)
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, width="stretch", height=400)
            if sheet.max_row > 50:
                st.caption(f"先頭 50 行を表示中（全 {sheet.max_row:,} 行）")
    except ImportError:
        st.info("pandas が利用できないため、テーブルプレビューを表示できません。")


def _render_pandas_preview(file_name: str, file_bytes: bytes) -> None:
    """pandas を使った簡易プレビュー。"""
    try:
        import pandas as pd

        st.info("コアモジュールが利用できないため、pandas による簡易プレビューを表示しています。")

        if file_name.endswith(".xlsx"):
            xls = pd.ExcelFile(BytesIO(file_bytes))
            sheet_names = xls.sheet_names
            selected = st.selectbox("📋 シートを選択", sheet_names)
            df = pd.read_excel(BytesIO(file_bytes), sheet_name=selected, header=None)
        elif file_name.endswith(".tsv"):
            df = pd.read_csv(BytesIO(file_bytes), sep="\t", header=None)
        else:
            df = pd.read_csv(BytesIO(file_bytes), header=None)

        col1, col2 = st.columns(2)
        col1.metric("行数", f"{len(df):,}")
        col2.metric("列数", f"{len(df.columns):,}")

        st.dataframe(df, width="stretch", height=400)
    except Exception as e:
        st.error(f"プレビューの表示に失敗しました: {e}")
