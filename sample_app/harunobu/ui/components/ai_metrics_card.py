"""AI利用メトリクス表示コンポーネント"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from harunobu.core.ai_metrics import AIMetricsSummary


def render_ai_metrics(summary: AIMetricsSummary, label: str = "") -> None:
    """AI利用メトリクスをexpanderで表示する。"""
    if summary.total_calls == 0:
        return

    title = f"AI利用状況{f' ({label})' if label else ''}"
    with st.expander(title, expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("API呼出回数", f"{summary.total_calls} 回")
        col2.metric("合計処理時間", f"{summary.total_duration_sec:.1f} 秒")
        col3.metric(
            "トークン数",
            f"{summary.total_input_tokens + summary.total_output_tokens:,}",
            help=f"入力: {summary.total_input_tokens:,} / 出力: {summary.total_output_tokens:,}",
        )
        col4.metric("推定コスト", f"${summary.estimated_cost_usd:.4f}")

        if summary.failed_calls > 0:
            st.warning(f"失敗した呼び出し: {summary.failed_calls} 回")

        # 呼び出し内訳
        if summary.calls:
            _render_call_details(summary)


def _render_call_details(summary: AIMetricsSummary) -> None:
    """呼び出しの内訳テーブルを表示する。"""
    # メソッド別に集計
    method_stats: dict[str, dict] = {}
    for call in summary.calls:
        if call.method not in method_stats:
            method_stats[call.method] = {
                "count": 0,
                "duration": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "failed": 0,
            }
        stats = method_stats[call.method]
        stats["count"] += 1
        stats["duration"] += call.duration_sec
        stats["input_tokens"] += call.input_tokens
        stats["output_tokens"] += call.output_tokens
        if not call.success:
            stats["failed"] += 1

    rows = []
    for method, stats in sorted(method_stats.items()):
        rows.append(
            {
                "メソッド": method,
                "回数": stats["count"],
                "処理時間(秒)": round(stats["duration"], 1),
                "入力トークン": stats["input_tokens"],
                "出力トークン": stats["output_tokens"],
                "失敗": stats["failed"],
            }
        )

    try:
        import pandas as pd

        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    except ImportError:
        for row in rows:
            st.text(
                f"{row['メソッド']}: {row['回数']}回, "
                f"{row['処理時間(秒)']}秒, "
                f"tokens={row['入力トークン']}+{row['出力トークン']}"
            )
