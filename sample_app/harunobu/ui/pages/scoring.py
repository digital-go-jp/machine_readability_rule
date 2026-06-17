"""チェック実行ページ"""

from __future__ import annotations

import streamlit as st

from harunobu.core.models import _MODE_LEVELS
from harunobu.ui.safe_html import escape_html
from harunobu.ui.styles import page_header


def render() -> None:
    """チェック実行ページを描画する。"""
    page_header("🔍", "チェック実行", "ルールに基づいて機械可読性を採点します。")

    uploaded_files = st.session_state.get("uploaded_files") or []
    uploaded_file = st.session_state.get("uploaded_file")
    if not uploaded_files and uploaded_file is None:
        st.warning("ファイルがアップロードされていません。")
        if st.button("← アップロードに戻る"):
            st.session_state.workflow_step = "UPLOAD"
            st.rerun()
        return

    is_bulk = len(uploaded_files) >= 2

    # ファイル情報
    if is_bulk:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="info-card-label">対象ファイル（{len(uploaded_files)}件 bulk 採点）</div>'
            f'<div class="info-card-value info-card-value-compact">'
            f"📚 {escape_html(', '.join(f.name for f in uploaded_files[:5]))}"
            f"{' …' if len(uploaded_files) > 5 else ''}"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        ref = uploaded_file or uploaded_files[0]
        st.markdown(
            f'<div class="info-card">'
            f'<div class="info-card-label">対象ファイル</div>'
            f'<div class="info-card-value info-card-value-compact">📄 {escape_html(ref.name)}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # モード選択
    st.markdown("")
    st.markdown("**チェックのレベルを選択**")
    mode = st.radio(
        "チェックのレベル",
        options=["lite", "standard", "thorough"],
        index=1,
        format_func=_mode_label,
        horizontal=True,
        label_visibility="collapsed",
    )

    # チェック対象レベルの説明
    levels = _mode_levels(mode)
    level_badges = " ".join(f'<span class="badge badge-info">レベル {lv}</span>' for lv in levels)
    descriptions = {
        "lite": "基本的な構造チェックのみ（高速）",
        "standard": "構造 + データ品質チェック",
        "thorough": "構造 + データ品質 + 標準化チェック（最も詳細）",
    }
    st.markdown(
        f'チェック対象: {level_badges}<div class="mode-description">{descriptions[mode]}</div>',
        unsafe_allow_html=True,
    )

    # ナビゲーション
    # bulk 時は PREVIEW を飛ばして UPLOAD から直接来ているため、戻り先も UPLOAD にする。
    # 戻り先を PREVIEW にすると先頭ファイルだけの single-file プレビューに入り、
    # bulk セッションと state が混ざる。
    back_step = "UPLOAD" if is_bulk else "PREVIEW"
    back_label = "← アップロード" if is_bulk else "← データプレビュー"
    st.markdown("---")
    col1, _, col2 = st.columns([1, 2, 1])
    with col1:
        if st.button(back_label, width="stretch"):
            st.session_state.workflow_step = back_step
            st.rerun()
    with col2:
        if st.button("▶ チェック実行", type="primary", width="stretch"):
            _run_scoring(mode)


def _mode_label(mode: str) -> str:
    labels = {
        "lite": "⚡ 軽量チェック",
        "standard": "📊 標準チェック",
        "thorough": "🔬 詳細チェック",
    }
    return labels.get(mode, mode)


def _mode_levels(mode: str) -> list[int]:
    """モードに対応する評価対象レベルを昇順で返す（core の _MODE_LEVELS に従う）。"""
    return sorted(_MODE_LEVELS.get(mode, {1, 2, 3}))


def _run_scoring(mode: str) -> None:
    """採点を実行する。"""
    progress = st.progress(0, text="チェックを準備中...")

    uploaded_files = st.session_state.get("uploaded_files") or []
    is_bulk = len(uploaded_files) >= 2

    try:
        if is_bulk:
            bulk_result = _execute_bulk_analysis(mode, progress)
            st.session_state.bulk_analysis_result = bulk_result
            # シングルファイルビュー用に先頭ファイルの結果を設定
            if bulk_result.files:
                st.session_state.analysis_result = bulk_result.files[0]
        else:
            result = _execute_analysis(mode, progress)
            st.session_state.analysis_result = result
            st.session_state.bulk_analysis_result = None
        st.session_state.workflow_step = "RESULT"
        st.rerun()
    except Exception as e:
        st.error(f"チェック実行中にエラーが発生しました: {e}")


def _execute_analysis(mode: str, progress: st.delta_generator.DeltaGenerator):  # type: ignore[name-defined]
    """コアの Analyzer を呼び出す（単一ファイル）。"""
    from harunobu.core.ai_metrics import AIMetricsTracker
    from harunobu.core.analyzer import Analyzer  # type: ignore[import-not-found]

    AIMetricsTracker.reset()
    progress.progress(20, text="📚 ルールを読み込み中...")

    workbook = st.session_state.get("workbook")
    uploaded_files = st.session_state.get("uploaded_files") or []
    uploaded_file = st.session_state.get("uploaded_file") or (uploaded_files[0] if uploaded_files else None)
    file_bytes = uploaded_file.getvalue()

    analyzer = Analyzer(mode=mode)

    progress.progress(40, text="🔎 構造を解析中...")

    if workbook is not None:
        result = analyzer.analyze(workbook)
    else:
        from io import BytesIO

        result = analyzer.analyze_file(uploaded_file.name, BytesIO(file_bytes))

    st.session_state.ai_metrics_check = AIMetricsTracker.get_instance().get_summary()

    progress.progress(100, text="✅ 完了")
    return result


def _execute_bulk_analysis(mode: str, progress: st.delta_generator.DeltaGenerator):  # type: ignore[name-defined]
    """複数ファイルの bulk 分析を実行する。"""
    from io import BytesIO

    from harunobu.core.ai_metrics import AIMetricsTracker
    from harunobu.core.analyzer import Analyzer
    from harunobu.core.reader import read_workbook

    AIMetricsTracker.reset()
    progress.progress(10, text="📚 ルールを読み込み中...")

    uploaded_files = st.session_state.uploaded_files
    analyzer = Analyzer(mode=mode)

    workbooks = []
    n = len(uploaded_files)
    for i, f in enumerate(uploaded_files):
        progress.progress(
            10 + int(40 * (i + 1) / n),
            text=f"📖 ファイル読み込み中 ({i + 1}/{n}): {f.name}",
        )
        workbooks.append(read_workbook(f.name, BytesIO(f.getvalue())))

    progress.progress(60, text="🔎 ファイル個別分析中...")
    bulk_result = analyzer.analyze_bulk(workbooks)

    progress.progress(95, text="🔁 ファイル横断チェック完了")
    st.session_state.ai_metrics_check = AIMetricsTracker.get_instance().get_summary()

    progress.progress(100, text="✅ 完了")
    return bulk_result
