"""サイドバーナビゲーション"""

from __future__ import annotations

import streamlit as st

from harunobu.ui.safe_html import escape_html

WORKFLOW_STEPS = [
    ("UPLOAD", "ファイルアップロード", "📁"),
    ("PREVIEW", "データプレビュー", "👁"),
    ("VALIDATION", "レイアウト検出", "🔬"),
    ("SCORING", "チェック実行", "🔍"),
    ("RESULT", "採点結果", "📊"),
]


def render_sidebar() -> None:
    """サイドバーを描画する。"""
    with st.sidebar:
        # ブランドヘッダー
        st.markdown(
            '<h1 class="sidebar-title">機械可読性チェックツール</h1>',
            unsafe_allow_html=True,
        )
        st.caption("Harunobu")
        st.divider()

        current_step = st.session_state.get("workflow_step", "UPLOAD")
        current_idx = _step_index(current_step)

        # ワークフローステップ
        st.markdown(
            '<div class="sidebar-section-label">ワークフロー</div>',
            unsafe_allow_html=True,
        )

        for i, (step_key, step_label, step_icon) in enumerate(WORKFLOW_STEPS):
            step_num = i + 1
            if step_key == current_step:
                # 現在のステップ
                st.markdown(
                    f'<div class="step-item step-current">'
                    f'<span class="step-icon">{step_icon}</span>'
                    f"{step_num}. {step_label}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            elif i < current_idx:
                # 完了済みステップ — ボタンではなくHTMLで左揃え統一し、別途ボタンで遷移
                col_label, col_btn = st.columns([4, 1])
                with col_label:
                    st.markdown(
                        f'<div class="step-item step-done">'
                        f'<span class="step-icon">✅</span>'
                        f"{step_num}. {step_label}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("↩", key=f"nav_{step_key}", help=f"{step_label}に戻る"):
                        st.session_state.workflow_step = step_key
                        st.rerun()
            else:
                # 未到達ステップ
                st.markdown(
                    f'<div class="step-item step-future">'
                    f'<span class="step-icon">○</span>'
                    f"{step_num}. {step_label}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.divider()

        # ファイル情報
        uploaded_files = st.session_state.get("uploaded_files") or []
        single_uploaded = st.session_state.get("uploaded_file")
        if uploaded_files or single_uploaded is not None:
            st.markdown(
                '<div class="sidebar-section-label">アップロード済みファイル</div>',
                unsafe_allow_html=True,
            )
            if len(uploaded_files) >= 2:
                total_kb = sum(len(f.getvalue()) for f in uploaded_files) / 1024
                size_str = f"{total_kb:.1f} KB" if total_kb < 1024 else f"{total_kb / 1024:.1f} MB"
                st.markdown(
                    f'<div class="file-info">'
                    f'<div class="file-info-name">📚 {len(uploaded_files)} ファイル (bulk)</div>'
                    f'<div class="file-info-size">合計 {size_str}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                uploaded = single_uploaded or uploaded_files[0]
                size_kb = len(uploaded.getvalue()) / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
                st.markdown(
                    f'<div class="file-info">'
                    f'<div class="file-info-name">📄 {escape_html(uploaded.name)}</div>'
                    f'<div class="file-info-size">{size_str}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # スコア表示（採点済みの場合）— レベル別の最小値を主表示にする
        analysis = st.session_state.get("analysis_result")
        if analysis is not None:
            try:
                from harunobu.core.models import AnalysisResult, safe_validate
                from harunobu.core.scorer import LevelScorer
                from harunobu.ui.styles import score_bar_color, score_color_class

                result = safe_validate(AnalysisResult, analysis)
                scoring = LevelScorer().score_analysis(result)
                st.markdown(
                    '<div class="sidebar-score-block"><div class="sidebar-section-label">レベル別スコア</div></div>',
                    unsafe_allow_html=True,
                )
                for lv in (1, 2, 3):
                    ls = scoring.per_level[lv]
                    if ls.score is None:
                        st.markdown(
                            f'<div class="sidebar-score-missing">L{lv}: 未チェック</div>',
                            unsafe_allow_html=True,
                        )
                        continue
                    color_class = score_color_class(ls.score)
                    bar_color = score_bar_color(ls.score)
                    note = " (強制0点)" if ls.forced_zero else ""
                    st.markdown(
                        f'<div class="sidebar-score-block">'
                        f'<div class="sidebar-score-label">L{lv}{note}</div>'
                        f'<div class="sidebar-score-value score-number-{color_class}">{ls.score}</div>'
                        f'<div class="level-score-bar">'
                        f'<div class="level-score-fill" style="width:{ls.score}%; background:{bar_color};"></div>'
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass

        # リセットボタン
        if current_step != "UPLOAD":
            st.divider()
            if st.button("🔄 最初からやり直す", width="stretch"):
                for key in [
                    "workflow_step",
                    "uploaded_file",
                    "uploaded_files",
                    "active_file_index",
                    "workbook",
                    "analysis_result",
                    "bulk_analysis_result",
                    "ai_metrics_check",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()


def _step_index(step: str) -> int:
    """ステップのインデックスを返す。"""
    for i, (key, _, _) in enumerate(WORKFLOW_STEPS):
        if key == step:
            return i
    return 0
