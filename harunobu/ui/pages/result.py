"""採点結果表示ページ"""

from __future__ import annotations

import streamlit as st

from harunobu.core.models import AnalysisResult, WorkBook, safe_validate
from harunobu.output import csv_writer, json_writer
from harunobu.ui.components.ai_metrics_card import render_ai_metrics
from harunobu.ui.components.excel_grid import (
    NOTE_TITLE_REGION_TYPES,
    aggregate_violations_for_sheet,
    build_layout_cell_style,
    build_legend_html,
    extract_cell_maps,
    render_detected_grid_html,
)
from harunobu.ui.components.score_card import render_score_card
from harunobu.ui.safe_html import escape_html
from harunobu.ui.styles import page_header, section_header


def _render_bulk_summary(bulk_result) -> None:  # type: ignore[no-untyped-def]
    """bulk 評価のサマリーを表示する。

    bulk total を主スコアとして冒頭で大きく表示し、その下に各ファイルの
    平均スコアとファイル横断チェック結果を並べる。
    """
    section_header("📚", f"複数ファイル評価サマリー（{bulk_result.file_count}ファイル）")

    # bulk total を主役表示
    total = bulk_result.total_score
    st.markdown(
        f'<div class="info-card">'
        f'<div class="info-card-label">複数ファイル総合スコア（ファイル平均×0.7 + 横断チェック×0.3）</div>'
        f'<div class="info-card-value info-card-value-large">{total}/100</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    per_file_scores = bulk_result.per_file_scores()
    cols = st.columns(min(bulk_result.file_count, 5))
    for i, file_result in enumerate(bulk_result.files):
        score = per_file_scores[i]
        score_label = f"{score}/100" if score is not None else "—"
        with cols[i % len(cols)]:
            st.markdown(
                f'<div class="info-card">'
                f'<div class="info-card-label break-all">'
                f"{escape_html(file_result.file_meta.name)}</div>"
                f'<div class="info-card-value">{escape_html(score_label)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    bulk_checks = getattr(bulk_result, "bulk_checks", {})
    if bulk_checks:
        st.markdown("**ファイル横断チェック結果**")
        for rule_id, cr in bulk_checks.items():
            badge = "✅ 合格" if cr.passed else f"⚠️ {len(cr.violations)}件の違反"
            st.markdown(f"- **{rule_id}**: {badge} — {cr.message}")
            for v in cr.violations:
                st.markdown(f"    - [{v.severity}] {v.description}")


def render() -> None:
    """採点結果表示ページを描画する。"""
    page_header("📊", "採点結果")

    bulk_result = st.session_state.get("bulk_analysis_result")
    raw_result = st.session_state.get("analysis_result")
    if bulk_result is None and raw_result is None:
        st.warning("採点結果がありません。チェックを実行してください。")
        if st.button("← チェック実行に戻る"):
            st.session_state.workflow_step = "SCORING"
            st.rerun()
        return

    # bulk モードの場合: ファイル切替タブ + bulk セクション
    if bulk_result is not None and getattr(bulk_result, "file_count", 0) >= 2:
        _render_bulk_summary(bulk_result)
        st.markdown("---")
        file_names = [f.file_meta.name for f in bulk_result.files]
        if st.session_state.active_file_index >= len(file_names):
            st.session_state.active_file_index = 0
        st.radio(
            "📂 表示中のファイル",
            options=list(range(len(file_names))),
            format_func=lambda i: file_names[i],
            key="active_file_index",
            horizontal=True,
        )
        new_idx = st.session_state.active_file_index
        result = bulk_result.files[new_idx]
        # サイドバーのスコア表示をファイル切替に追随させる。インデックスが変化した
        # 場合のみ書き込み、毎 rerun での不要な session_state 更新を避ける。
        if st.session_state.get("_sidebar_file_idx") != new_idx:
            st.session_state.analysis_result = result
            st.session_state._sidebar_file_idx = new_idx
    else:
        try:
            result = safe_validate(AnalysisResult, raw_result)
        except Exception:
            st.error("採点結果の解析に失敗しました。チェックを再実行してください。")
            return

    # スコアカード
    render_score_card(result)

    # 違反箇所
    st.markdown("---")
    _render_violations(result)

    # シート別の違反セル + レイアウト可視化
    st.markdown("---")
    _render_per_sheet_visualization(result)

    # AIメトリクス
    _render_ai_metrics("ai_metrics_check", "チェック時")

    # ダウンロード
    st.markdown("---")
    if bulk_result is not None and getattr(bulk_result, "file_count", 0) >= 2:
        _render_bulk_download(bulk_result)
    else:
        _render_download(result)

    # ナビゲーション
    st.markdown("---")
    if st.button("← チェック実行", width="stretch"):
        st.session_state.workflow_step = "SCORING"
        st.rerun()


def _render_violations(result: AnalysisResult) -> None:
    """違反箇所の一覧を表示する。"""
    section_header("⚠️", "違反箇所")

    violations_data: list[dict[str, str]] = []
    real_total = 0  # 全ルールの違反実件数（切り捨て前）
    has_truncated = False  # いずれかのルールで要約表示が発生したか

    for sheet_result in result.sheets:
        for table in sheet_result.tables:
            for rule_id, check in table.mr_result.all_results().items():
                real_total += len(check.violations)
                if check.is_display_truncated:
                    has_truncated = True
                    # グループ（sheet × severity）を 1 行ずつ展開
                    for g in check.violation_groups:
                        sample_range = g.samples[0].cell_range if g.samples else "-"
                        violations_data.append(
                            {
                                "ルールID": rule_id,
                                "シート": g.sheet,
                                "セル範囲": f"{sample_range} 他",
                                "重大度": g.severity,
                                "説明": f"【要約】{g.count} 件（代表: {sample_range}）",
                                "件数": str(g.count),
                            }
                        )
                else:
                    for v in check.violations:
                        violations_data.append(
                            {
                                "ルールID": rule_id,
                                "シート": v.sheet,
                                "セル範囲": v.cell_range,
                                "重大度": v.severity,
                                "説明": v.description,
                                "件数": "",
                            }
                        )

    if not violations_data:
        st.success("✅ 違反箇所は見つかりませんでした。")
        return

    # 重大度別の集計（実件数ベース）
    severity_counts: dict[str, int] = {}
    for sheet_result in result.sheets:
        for table in sheet_result.tables:
            for check in table.mr_result.all_results().values():
                for v in check.violations:
                    severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1

    # サマリーバッジ（実件数を使用）
    badge_html = f'<span class="badge badge-fail">{real_total} 件の違反</span> '
    for sev, count in sorted(severity_counts.items()):
        variant = "fail" if sev in ("error", "エラー") else "warn" if sev in ("warning", "警告") else "info"
        badge_html += f'<span class="badge badge-{variant}">{escape_html(sev)}: {count}</span> '
    st.markdown(badge_html, unsafe_allow_html=True)

    # 要約表示の注記
    if has_truncated:
        st.info(
            "ℹ️ 件数が多いルールはシート／重大度単位で要約表示しています。"
            "違反全件の詳細は JSON ダウンロードを参照してください（CSV は要約のみ掲載されています）。"
        )

    st.markdown("")

    try:
        import pandas as pd

        df = pd.DataFrame(violations_data)
        st.dataframe(
            df,
            width="stretch",
            column_config={
                "重大度": st.column_config.TextColumn(width="small"),
                "ルールID": st.column_config.TextColumn(width="small"),
                "セル範囲": st.column_config.TextColumn(width="small"),
                "件数": st.column_config.TextColumn(width="small"),
            },
        )
    except ImportError:
        for v in violations_data:
            st.markdown(f"- **{v['ルールID']}** ({v['重大度']}): {v['シート']} {v['セル範囲']} - {v['説明']}")


def _render_per_sheet_visualization(result: AnalysisResult) -> None:
    """シートごとにレイアウト検出結果と違反セルを重ねて表示する。

    ``st.session_state.workbook`` が単一ファイルモード時にだけ参照可能なため、
    存在しない/別ファイルのワークブックの場合は注意書きを表示するに留める。
    """
    section_header("📍", "シート別 違反セル表示")
    st.caption(
        "レイアウト推定結果（テーブル領域・ヘッダー/ボディ）と、各ルールの違反セルを"
        "シート上で重ねて確認できます。違反セルには重大度別の枠線とルールIDバッジを表示します。"
    )

    if not result.sheets:
        st.info("シート情報がありません。")
        return

    raw_wb = st.session_state.get("workbook")
    workbook: WorkBook | None
    try:
        workbook = safe_validate(WorkBook, raw_wb) if raw_wb is not None else None
    except Exception:
        workbook = None

    if workbook is None or workbook.file_name != result.file_meta.name:
        st.info(
            "シート可視化を表示するにはワークブックデータが必要です。"
            "複数ファイル一括モードでは現在の表示対象ファイルを単独で再アップロードしてご確認ください。"
        )
        return

    sheet_violation_counts: dict[str, int] = {}
    for sr in result.sheets:
        cnt = 0
        for tbl in sr.tables:
            for check in tbl.mr_result.all_results().values():
                cnt += len(check.violations)
        sheet_violation_counts[sr.sheet_meta.name] = cnt

    sheet_names = [sr.sheet_meta.name for sr in result.sheets]

    def _fmt(name: str) -> str:
        cnt = sheet_violation_counts.get(name, 0)
        if cnt == 0:
            return f"{name}（違反なし）"
        return f"{name}（違反 {cnt} 件）"

    # 違反の多いシートを先頭に
    sheet_names_sorted = sorted(sheet_names, key=lambda n: -sheet_violation_counts.get(n, 0))
    selected = st.selectbox(
        "シートを選択",
        sheet_names_sorted,
        format_func=_fmt,
        key="result_viz_sheet",
    )

    sheet_result = next(
        (sr for sr in result.sheets if sr.sheet_meta.name == selected),
        None,
    )
    if sheet_result is None:
        st.warning(f"シート「{selected}」の採点結果が見つかりません。")
        return

    sheet = workbook.get_sheet(selected)
    if sheet is None:
        st.warning(f"シート「{selected}」のセルデータが見つかりません。")
        return

    max_row = min(sheet.max_row, 200)
    max_col = min(sheet.max_col, 50)
    if max_row <= 0 or max_col <= 0:
        st.info("このシートには表示可能なセルがありません。")
        return

    violation_cells, unrenderable_count = aggregate_violations_for_sheet(sheet_result)
    cell_values, cell_bold, _cell_merged = extract_cell_maps(sheet, max_row, max_col)
    cell_style = build_layout_cell_style(sheet_result.tables, sheet_result.others, max_row, max_col)

    if not sheet_result.tables and not sheet_result.others:
        st.caption("このシートではレイアウトが検出されませんでした。違反セルがある場合のみハイライト表示します。")

    st.caption("ハイライト")
    highlight_cols = st.columns(3)
    with highlight_cols[0]:
        show_table_highlight = st.checkbox("テーブル", value=True, key="result_viz_highlight_tables")
    with highlight_cols[1]:
        show_violation_highlight = st.checkbox("違反箇所", value=True, key="result_viz_highlight_violations")
    with highlight_cols[2]:
        show_note_title_highlight = st.checkbox("note/title", value=True, key="result_viz_highlight_note_title")

    highlighted_other_types = NOTE_TITLE_REGION_TYPES if show_note_title_highlight else frozenset()
    visible_violation_cells = violation_cells if show_violation_highlight else None

    grid_html = render_detected_grid_html(
        cell_values,
        cell_bold,
        cell_style,
        max_row,
        max_col,
        violation_cells=visible_violation_cells,
        show_table_highlight=show_table_highlight,
        highlighted_other_types=highlighted_other_types,
    )
    legend_html = build_legend_html(
        sheet_result.tables,
        sheet_result.others,
        include_violations=show_violation_highlight and bool(violation_cells),
        show_tables=show_table_highlight,
        highlighted_other_types=highlighted_other_types,
    )
    st.markdown(grid_html + legend_html, unsafe_allow_html=True)

    if unrenderable_count > 0:
        st.caption(
            f"⚠ {unrenderable_count} 件の違反はグリッドに描画できませんでした"
            "（cell_range が範囲指定外/非対応形式）。違反一覧テーブルでご確認ください。"
        )

    if sheet.max_row > max_row or sheet.max_col > max_col:
        st.caption(
            f"表示は {max_row}行 × {max_col}列 までに制限されています （実際: {sheet.max_row}行 × {sheet.max_col}列）。"
        )


def _render_ai_metrics(session_key: str, label: str) -> None:
    """セッションに保存されたAIメトリクスを表示する。"""
    summary = st.session_state.get(session_key)
    if summary is not None:
        render_ai_metrics(summary, label=label)


def _render_download(result: AnalysisResult) -> None:
    """結果のダウンロードボタンを表示する。

    出力は ``json_writer`` / ``csv_writer`` を経由し、スキーマ定義の日本語キーと
    レベル別スコア・強制0点情報を含む形式で提供する。
    """
    section_header("💾", "結果ダウンロード")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📥 JSON でダウンロード",
            data=json_writer.to_json(result),
            file_name="採点結果.json",
            mime="application/json",
            width="stretch",
        )

    with col2:
        st.download_button(
            label="📥 CSV でダウンロード",
            data=csv_writer.to_csv_string(result),
            file_name="採点結果.csv",
            mime="text/csv",
            width="stretch",
        )


def _render_bulk_download(bulk_result) -> None:  # type: ignore[no-untyped-def]
    """bulk モード結果のダウンロードボタンを表示する。

    複数ファイル総合スコアとファイル横断チェック結果を含む形式で出力する。
    画面に表示されている bulk total / bulk_checks と一致させる目的。
    """
    section_header("💾", "結果ダウンロード（複数ファイル）")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📥 JSON でダウンロード（bulk）",
            data=json_writer.to_bulk_json(bulk_result),
            file_name="採点結果_bulk.json",
            mime="application/json",
            width="stretch",
        )

    with col2:
        st.download_button(
            label="📥 CSV でダウンロード（bulk）",
            data=csv_writer.to_bulk_csv_string(bulk_result),
            file_name="採点結果_bulk.csv",
            mime="text/csv",
            width="stretch",
        )
