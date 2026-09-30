"""レイアウト検出バリデーションページ

アップロード済みファイルに対してレイアウト検出を実行し、
元データと検出結果を並べて可視化する。
"""

from __future__ import annotations

import streamlit as st

from harunobu.core.layout import LayoutDetector
from harunobu.core.models import Config, Sheet, WorkBook
from harunobu.ui.components.excel_grid import (
    DEFAULT_TYPE_BADGE_COLOR,
    TYPE_BADGE_COLOR,
    build_layout_cell_style,
    build_legend_html,
    col_letter,
    extract_cell_maps,
    render_detected_grid_html,
    render_raw_grid_html,
)
from harunobu.ui.safe_html import escape_html
from harunobu.ui.styles import page_header
from harunobu.ui.theme_tokens import token_var


def render() -> None:
    """レイアウト検出バリデーションページを描画する。"""
    page_header(
        "🔬",
        "レイアウト検出バリデーション",
        "アップロードされたファイルに対してレイアウト検出を実行し、検出結果を可視化します。",
    )

    workbook: WorkBook | None = st.session_state.get("workbook")
    if workbook is None:
        st.warning("ファイルがアップロードされていません。先にファイルをアップロードしてください。")
        if st.button("← アップロードに戻る"):
            st.session_state.workflow_step = "UPLOAD"
            st.rerun()
        return

    # レイアウト検出実行
    detection_results = _run_detection(workbook)

    # シート選択
    sheet_names = [s.name for s in workbook.sheets]
    selected_sheet_name = st.selectbox("シートを選択", sheet_names)
    selected_idx = sheet_names.index(selected_sheet_name)
    sheet = workbook.sheets[selected_idx]
    result = detection_results[selected_idx]

    # ファイル情報
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
            f'<div class="info-card-label">検出テーブル数</div>'
            f'<div class="info-card-value">{len(result.tables)}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="info-card-label">テーブル外セル</div>'
            f'<div class="info-card-value">{len(result.others)}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # グリッド表示
    _render_sheet(sheet, result)

    # ナビゲーション
    st.markdown("---")
    col1, _, col2 = st.columns([1, 2, 1])
    with col1:
        if st.button("← プレビュー", width="stretch"):
            st.session_state.workflow_step = "PREVIEW"
            st.rerun()
    with col2:
        if st.button("チェック実行 →", type="primary", width="stretch"):
            st.session_state.workflow_step = "SCORING"
            st.rerun()


@st.cache_data
def _run_detection_cached(file_name: str, sheet_count: int) -> None:
    """キャッシュキー用のダミー（実際の検出は _run_detection で行う）"""
    return None


def _run_detection(workbook: WorkBook) -> list:
    """全シートに対してレイアウト検出を実行する。"""
    cache_key = f"validation_results_{id(workbook)}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    config = Config()
    detector = LayoutDetector(config)
    results = []
    for sheet in workbook.sheets:
        result = detector.detect_with_others(sheet)
        results.append(result)

    st.session_state[cache_key] = results
    return results


def _render_sheet(sheet: Sheet, result) -> None:
    """シートの元データと検出結果を表示する。"""
    max_row = min(sheet.max_row, 200)
    max_col = min(sheet.max_col, 50)

    cell_values, cell_bold, cell_merged = extract_cell_maps(sheet, max_row, max_col)

    st.markdown(f"### {sheet.name} &nbsp; ({sheet.max_row}行 × {sheet.max_col}列)")

    tab_raw, tab_detected = st.tabs(["元データ", "検出結果"])

    with tab_raw:
        st.markdown(
            render_raw_grid_html(cell_values, cell_bold, cell_merged, max_row, max_col),
            unsafe_allow_html=True,
        )

    with tab_detected:
        cell_style = build_layout_cell_style(result.tables, result.others, max_row, max_col)
        grid_html = render_detected_grid_html(cell_values, cell_bold, cell_style, max_row, max_col)
        legend_html = build_legend_html(result.tables, result.others)
        st.markdown(grid_html + legend_html, unsafe_allow_html=True)

    # テーブル構造詳細
    if result.tables:
        st.markdown("---")
        st.subheader("検出されたテーブル構造")
        for i, table in enumerate(result.tables):
            _render_table_detail(i, table)

    if result.others:
        st.markdown("---")
        st.subheader("検出された Others（テーブル外セル）")
        _render_others_detail(result.others)


# ─── テーブル詳細 ───


def _render_table_detail(idx: int, table) -> None:
    conf_pct = f"{table.confidence * 100:.0f}%"
    header_str = ", ".join(str(r) for r in table.layout.header_rows)

    with st.expander(f"T{idx + 1}: {table.range}  (検出精度={conf_pct})", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**範囲:** `{table.range}`")
        c2.markdown(f"**ヘッダー行:** `[{header_str}]`")
        c3.markdown(f"**ボディ:** 行 {table.layout.body_start_row}〜{table.layout.body_end_row}")
        c4.markdown(f"**検出精度:** {conf_pct}")

        # 列型サマリ
        columns = table.layout.columns
        if columns:
            type_counts: dict[str, int] = {}
            for col_info in columns:
                t = col_info.inferred_type
                type_counts[t] = type_counts.get(t, 0) + 1
            badges = " ".join(
                f'<span class="html-badge" style="background:{TYPE_BADGE_COLOR.get(t, DEFAULT_TYPE_BADGE_COLOR)};'
                f'color:{token_var("color-surface")};">{escape_html(t)} x{n}</span>'
                for t, n in sorted(type_counts.items())
            )
            st.markdown(f"**列型分布:** {badges}", unsafe_allow_html=True)

        headers = table.layout.column_headers
        if headers or columns:
            import pandas as pd

            rows = []
            for i, ch in enumerate(headers):
                cs = columns[i] if i < len(columns) else None
                rows.append(
                    {
                        "列": col_letter(ch.col_index),
                        "ラベル": ch.label,
                        "結合": "Yes" if ch.is_merged else "",
                        "推定型": cs.inferred_type if cs else "",
                        "ヘッダー有": "Yes" if (cs and cs.has_header) else "No",
                    }
                )
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_others_detail(others: list) -> None:
    import pandas as pd

    rows = []
    for o in others:
        rows.append(
            {
                "セル": f"{col_letter(o.col)}{o.row}",
                "値": str(o.value) if o.value is not None else "",
                "種別": o.region_type,
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
