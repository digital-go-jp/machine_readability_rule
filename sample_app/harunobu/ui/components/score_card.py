"""スコア表示コンポーネント

総合スコアは表示せず、レベル別スコアと OK/NG + severity を中心にする。
強制 0 点になったレベルには理由を明示する。
"""

from __future__ import annotations

import streamlit as st

from harunobu.core.models import AnalysisResult, CheckResult
from harunobu.core.scorer import LevelScore, LevelScorer
from harunobu.core.severity import Severity
from harunobu.rules.registry import registry
from harunobu.ui.safe_html import escape_html
from harunobu.ui.styles import score_bar_color, score_color_class
from harunobu.ui.theme_tokens import token_var


def render_score_card(result: AnalysisResult) -> None:
    """レベル別スコアと OK/NG をカード形式で表示する。"""
    scoring = LevelScorer().score_analysis(result)

    # レベル別スコア — 3カラムで主役表示
    lv_cols = st.columns(3)
    for col, lv in zip(lv_cols, (1, 2, 3)):
        with col:
            _render_level_score_card(scoring.per_level[lv])

    # 強制 0 点の説明バナー
    forced = [ls for ls in scoring.per_level.values() if ls.forced_zero]
    if forced:
        with st.container():
            for ls in forced:
                # 同一ルールが複数テーブルで失敗すると重複するため rule_id で重複除外する
                unique_rules = {fr.rule_id: fr for fr in ls.forced_zero_rules}.values()
                rules_str = ", ".join(f"{fr.rule_id}（{_severity_badge_label(fr.severity)}）" for fr in unique_rules)
                st.error(
                    f"**レベル {ls.level} は強制 0 点です。** 重大ルール（{rules_str}）に違反したためです。",
                    icon="🚨",
                )

    # シートごと・テーブルごとの個別ルール OK/NG
    for sheet_result in result.sheets:
        sheet_name = sheet_result.sheet_meta.name
        for i, table in enumerate(sheet_result.tables):
            table_label = f"📋 {sheet_name} — テーブル {i + 1}"
            with st.expander(table_label, expanded=len(result.sheets) == 1):
                _render_table_results(table.mr_result.level1, "レベル 1", 1)
                _render_table_results(table.mr_result.level2, "レベル 2", 2)
                _render_table_results(table.mr_result.level3, "レベル 3", 3)


def _render_level_score_card(ls: LevelScore) -> None:
    """1 レベル分のスコアカードを描画。"""
    if ls.score is None:
        st.markdown(
            f'<div class="info-card text-center">'
            f'<div class="info-card-label">レベル {ls.level}</div>'
            f'<div class="info-card-value" style="color:{token_var("color-disabled-text")};">—</div>'
            f'<div class="muted-text">未チェック</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    bar_color = score_bar_color(ls.score)
    color_class = score_color_class(ls.score)
    forced_tag = '<div class="score-forced">強制 0 点</div>' if ls.forced_zero else ""
    st.markdown(
        f'<div class="info-card text-center">'
        f'<div class="info-card-label">レベル {ls.level}</div>'
        f'<div class="info-card-value score-number-{color_class}">{ls.score}</div>'
        f'<div class="level-score-bar">'
        f'<div class="level-score-fill" style="width:{ls.score}%; background:{bar_color};"></div>'
        f"</div>"
        f'<div class="score-meta">合格 {ls.passed} / {ls.total}</div>'
        f"{forced_tag}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_table_results(results: dict[str, CheckResult], level_label: str, level_num: int) -> None:
    """レベルごとの個別ルール OK/NG を表示する（点数は出さない）。"""
    if not results:
        return

    active = {rid: c for rid, c in results.items() if c.confidence > 0}
    skipped_count = len(results) - len(active)
    passed = sum(1 for c in active.values() if c.passed)
    total = len(active)

    level_icon = ["", "🏗️", "📐", "🔬"][level_num]
    skipped_badge = _badge_html(
        token_var("color-disabled-bg"),
        token_var("color-disabled-text"),
        f"判定対象外 {skipped_count}件",
    )
    st.markdown(
        f"**{level_icon} {level_label}** "
        f'<span class="badge badge-pass">{passed} 合格</span> '
        + (f'<span class="badge badge-fail">{total - passed} 不合格</span>' if passed < total else "")
        + (f" {skipped_badge}" if skipped_count > 0 else ""),
        unsafe_allow_html=True,
    )

    cards_html = "".join(_rule_result_card_html(rule_id, check) for rule_id, check in sorted(results.items()))
    st.markdown(f'<div class="rule-card-grid">{cards_html}</div>', unsafe_allow_html=True)

    st.markdown("")  # spacer


def _get_rule_tooltip(rule_id: str) -> str:
    """rule_id からツールチップ用テキストを生成する。"""
    if not registry.get_all():
        registry.discover()
    try:
        rule = registry.get(rule_id)
        return f"{rule.rule_name}\n{rule.description}"
    except KeyError:
        return ""


def _rule_result_card_html(rule_id: str, check: CheckResult) -> str:
    tooltip = _get_rule_tooltip(rule_id)
    if check.confidence == 0:
        skipped_rule_badge = _badge_html(
            token_var("color-disabled-bg"),
            token_var("color-disabled-text"),
            "判定対象外",
        )
        return _check_tile_html(
            rule_id,
            "—",
            "rule-card-body-skipped",
            skipped_rule_badge,
            check.message,
            tooltip,
        )

    icon, body_class = ("✅", "rule-card-body-pass") if check.passed else ("❌", "rule-card-body-fail")
    return _check_tile_html(
        rule_id,
        icon,
        body_class,
        _severity_html(check.effective_severity, passed=check.passed),
        check.message,
        tooltip,
    )


def _severity_badge_label(severity: Severity) -> str:
    """severity の日本語ラベル。"""
    return {
        Severity.FATAL: "致命的",
        Severity.CRITICAL: "重大",
        Severity.MAJOR: "高",
        Severity.MINOR: "中",
        Severity.INFO: "情報",
    }.get(severity, severity.value)


_SEVERITY_BG = {
    Severity.FATAL: (token_var("color-severity-fatal"), token_var("color-surface")),
    Severity.CRITICAL: (token_var("color-error"), token_var("color-surface")),
    Severity.MAJOR: (token_var("color-warning"), token_var("color-surface")),
    Severity.MINOR: (token_var("color-warning-yellow-bg"), token_var("color-text")),
    Severity.INFO: (token_var("color-info"), token_var("color-surface")),
}


def _badge_html(bg: str, fg: str, label: str) -> str:
    return f'<span class="html-badge" style="background:{bg}; color:{fg};">{escape_html(label)}</span>'


def _severity_html(severity: Severity, passed: bool = False) -> str:
    if passed:
        bg, fg = token_var("color-passed-badge-bg"), token_var("color-disabled-text")
    else:
        bg, fg = _SEVERITY_BG.get(severity, (token_var("color-text-muted"), token_var("color-surface")))
    return _badge_html(bg, fg, _severity_badge_label(severity))


def _check_tile_html(
    rule_id: str, icon: str, body_class: str, badge: str, message: str | None, tooltip: str = ""
) -> str:
    tooltip_attr = f' data-tooltip="{escape_html(tooltip)}"' if tooltip else ""
    return (
        f'<div class="rule-card-body {body_class}"{tooltip_attr}>'
        f'<div class="rule-id">{escape_html(icon)} {escape_html(rule_id)}</div>'
        f"<div>{badge}</div>"
        + (f'<div class="rule-message">{escape_html(message)}</div>' if message else "")
        + "</div>"
    )
