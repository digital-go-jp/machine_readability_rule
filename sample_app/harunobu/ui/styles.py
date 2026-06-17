"""カスタムCSS・スタイル定義"""

from __future__ import annotations

import streamlit as st

from harunobu.ui.safe_html import escape_html
from harunobu.ui.theme_tokens import css_custom_properties, token_var

_CUSTOM_CSS = (
    "<style>\n"
    + css_custom_properties()
    + """
html,
body,
[class*="css"] {
    color: var(--dads-color-text);
    font-family: var(--dads-font-sans);
}

code,
pre,
kbd,
samp {
    font-family: var(--dads-font-mono);
}

/* ===== メインコンテンツ ===== */
section.main .block-container {
    max-width: min(1200px, 100%);
    padding-left: var(--dads-space-8);
    padding-right: var(--dads-space-8);
    padding-top: var(--dads-space-8);
}

@media (max-width: 768px) {
    section.main .block-container {
        padding-left: var(--dads-space-4);
        padding-right: var(--dads-space-4);
    }
}

/* ===== サイドバー ===== */
section[data-testid="stSidebar"] {
    background: var(--dads-color-surface);
    border-right: 1px solid var(--dads-color-border);
}
section[data-testid="stSidebar"] .stMarkdown h1,
.sidebar-title {
    color: var(--dads-color-text);
    font-size: var(--dads-font-size-2xl);
    font-weight: 700;
    letter-spacing: 0;
    line-height: 1.3;
    margin: 0;
}
.sidebar-section-label {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
    font-weight: 700;
    letter-spacing: 0;
    margin-bottom: var(--dads-space-2);
}
section[data-testid="stSidebar"] button,
section[data-testid="stSidebar"] button p,
section[data-testid="stSidebar"] button span,
section[data-testid="stSidebar"] button div,
section[data-testid="stSidebar"] .stButton button,
section[data-testid="stSidebar"] .stButton button p {
    justify-content: flex-start !important;
    text-align: left !important;
}
section[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    justify-content: flex-start !important;
    text-align: left !important;
}

/* ===== プライマリボタン ===== */
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
    background: var(--dads-color-button-primary-bg) !important;
    border-color: var(--dads-color-button-primary-border) !important;
    color: var(--dads-color-button-primary-text) !important;
}
button[kind="primary"] *,
button[data-testid="stBaseButton-primary"] * {
    color: inherit !important;
}
button[kind="primary"]:hover:not(:disabled),
button[data-testid="stBaseButton-primary"]:hover:not(:disabled),
div[data-testid="stButton"] button[kind="primary"]:hover:not(:disabled),
div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
    background: var(--dads-color-button-primary-hover-bg) !important;
    border-color: var(--dads-color-button-primary-hover-border) !important;
    color: var(--dads-color-button-primary-hover-text) !important;
}
button[kind="primary"]:focus-visible:not(:disabled),
button[data-testid="stBaseButton-primary"]:focus-visible:not(:disabled),
div[data-testid="stButton"] button[kind="primary"]:focus-visible:not(:disabled),
div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:focus-visible:not(:disabled) {
    outline: 3px solid var(--dads-color-button-primary-focus-ring) !important;
    outline-offset: 2px !important;
}
button[kind="primary"]:active:not(:disabled),
button[data-testid="stBaseButton-primary"]:active:not(:disabled),
div[data-testid="stButton"] button[kind="primary"]:active:not(:disabled),
div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:active:not(:disabled) {
    background: var(--dads-color-button-primary-active-bg) !important;
    border-color: var(--dads-color-button-primary-active-bg) !important;
    color: var(--dads-color-button-primary-hover-text) !important;
}
button[kind="primary"]:disabled,
button[data-testid="stBaseButton-primary"]:disabled,
div[data-testid="stButton"] button[kind="primary"]:disabled,
div[data-testid="stButton"] button[data-testid="stBaseButton-primary"]:disabled {
    background: var(--dads-color-disabled-bg) !important;
    border-color: var(--dads-color-disabled-border) !important;
    color: var(--dads-color-disabled-text) !important;
}

/* ===== ワークフローステップ ===== */
.step-item {
    align-items: center;
    border-radius: var(--dads-radius-card);
    display: flex;
    font-size: var(--dads-font-size-sm);
    gap: var(--dads-space-2);
    margin: var(--dads-space-1) 0;
    padding: var(--dads-space-2) var(--dads-space-3);
    text-align: left;
    transition: background 0.15s;
}
.step-current {
    background: var(--dads-color-primary-subtle);
    border-left: 4px solid var(--dads-color-primary);
    color: var(--dads-color-primary-hover);
    font-weight: 700;
}
.step-done {
    color: var(--dads-color-success);
}
.step-future {
    color: var(--dads-color-disabled-text);
}
.step-icon {
    flex-shrink: 0;
    text-align: center;
    width: 24px;
}

/* ===== ページヘッダー ===== */
.page-header {
    align-items: center;
    display: flex;
    gap: var(--dads-space-3);
    margin-bottom: var(--dads-space-2);
}
.page-header-icon {
    font-size: var(--dads-font-size-3xl);
}
.page-header-title {
    color: var(--dads-color-text);
    font-size: var(--dads-font-size-3xl);
    font-weight: 700;
    letter-spacing: 0;
    line-height: 1.35;
}
.page-description {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-base);
    line-height: 1.6;
    margin-bottom: var(--dads-space-6);
}

/* ===== スコアカード ===== */
.score-hero {
    border-radius: var(--dads-radius-card);
    margin-bottom: var(--dads-space-4);
    padding: var(--dads-space-6) var(--dads-space-4);
    text-align: center;
}
.score-hero-excellent {
    background: var(--dads-color-success-bg);
    border: 1px solid var(--dads-color-success-border);
}
.score-hero-good {
    background: var(--dads-color-info-bg);
    border: 1px solid var(--dads-color-info-border);
}
.score-hero-warning {
    background: var(--dads-color-warning-bg);
    border: 1px solid var(--dads-color-warning-border);
}
.score-hero-danger {
    background: var(--dads-color-error-bg);
    border: 1px solid var(--dads-color-error-border);
}
.score-number {
    font-size: var(--dads-font-size-score);
    font-weight: 800;
    line-height: 1;
    margin-bottom: var(--dads-space-1);
}
.score-number-excellent { color: var(--dads-color-success); }
.score-number-good { color: var(--dads-color-info); }
.score-number-warning { color: var(--dads-color-warning); }
.score-number-danger { color: var(--dads-color-error); }
.score-label {
    font-size: var(--dads-font-size-base);
    font-weight: 600;
}
.score-sublabel {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
    margin-top: var(--dads-space-1);
}

/* ===== レベルスコアバー ===== */
.level-score-bar {
    background: var(--dads-color-disabled-bg);
    border-radius: var(--dads-radius-control);
    height: var(--dads-space-2);
    margin-top: var(--dads-space-1);
    overflow: hidden;
}
.level-score-fill {
    border-radius: var(--dads-radius-control);
    height: 100%;
    transition: width 0.5s ease;
}

/* ===== ステータスバッジ ===== */
.badge,
.html-badge {
    border-radius: var(--dads-radius-badge);
    display: inline-block;
    font-size: var(--dads-font-size-sm);
    font-weight: 700;
    letter-spacing: 0;
    line-height: 1.2;
    padding: var(--dads-space-1) var(--dads-space-2);
}
.badge-pass {
    background: var(--dads-color-success-bg);
    color: var(--dads-color-success);
}
.badge-fail {
    background: var(--dads-color-error-bg);
    color: var(--dads-color-error);
}
.badge-info {
    background: var(--dads-color-info-bg);
    color: var(--dads-color-info);
}
.badge-warn {
    background: var(--dads-color-warning-bg);
    color: var(--dads-color-warning);
}

/* ===== ファイルアップロード ===== */
.format-badges {
    display: flex;
    gap: var(--dads-space-2);
    margin-bottom: var(--dads-space-4);
}
.format-badge {
    background: var(--dads-color-surface-subtle);
    border: 1px solid var(--dads-color-border);
    border-radius: var(--dads-radius-small);
    color: var(--dads-color-text-subtle);
    font-size: var(--dads-font-size-sm);
    font-weight: 500;
    padding: var(--dads-space-1) var(--dads-space-2);
}

/* ===== 情報カード ===== */
.info-card {
    background: var(--dads-color-surface);
    border: 1px solid var(--dads-color-border);
    border-radius: var(--dads-radius-card);
    margin-bottom: var(--dads-space-4);
    padding: var(--dads-space-4) var(--dads-space-5);
}
.info-card-label {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
    font-weight: 700;
    letter-spacing: 0;
    margin-bottom: var(--dads-space-1);
    text-transform: uppercase;
}
.info-card-value {
    color: var(--dads-color-text);
    font-size: var(--dads-font-size-2xl);
    font-weight: 700;
    line-height: 1.35;
}
.info-card-value-compact { font-size: var(--dads-font-size-base); }
.info-card-value-large { font-size: var(--dads-font-size-4xl); }

/* ===== 違反テーブル ===== */
.severity-error {
    color: var(--dads-color-error);
    font-weight: 600;
}
.severity-warning {
    color: var(--dads-color-warning);
    font-weight: 600;
}
.severity-info {
    color: var(--dads-color-info);
    font-weight: 600;
}

/* ===== Excel grid legend ===== */
.grid-legend {
    color: var(--dads-color-text-subtle);
    display: grid;
    font-size: var(--dads-font-size-xs);
    gap: var(--dads-space-3);
    margin: var(--dads-space-3) 0 var(--dads-space-2);
}
.grid-legend-title {
    color: var(--dads-color-text);
    font-weight: 700;
}
.grid-legend-section {
    display: grid;
    gap: var(--dads-space-2);
}
.grid-legend-section-label {
    color: var(--dads-color-text-muted);
    font-weight: 700;
}
.grid-legend-table-list {
    display: grid;
    gap: var(--dads-space-2);
}
.grid-legend-row,
.grid-legend-generic-list,
.grid-legend-violation-group,
.grid-legend-violation-item {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--dads-space-2);
}
.grid-legend-range {
    color: var(--dads-color-text);
    min-width: 96px;
}
.grid-legend-chip {
    border: 2px solid;
    border-radius: var(--dads-radius-small);
    display: inline-flex;
    font-size: var(--dads-font-size-xs);
    line-height: 1.2;
    padding: var(--dads-space-1) var(--dads-space-2);
}
.grid-legend-muted-text {
    color: var(--dads-color-grid-excluded);
}
.grid-legend-violation-group {
    color: var(--dads-color-text);
}
.grid-legend-violation-swatch {
    background: var(--dads-color-surface);
    border: 3px solid;
    display: inline-block;
    height: 14px;
    width: 14px;
}

/* ===== ナビゲーションボタン ===== */
.nav-container {
    border-top: 1px solid var(--dads-color-border-subtle);
    display: flex;
    justify-content: space-between;
    margin-top: var(--dads-space-8);
    padding-top: var(--dads-space-4);
}

/* ===== その他 ===== */
.section-header {
    align-items: center;
    color: var(--dads-color-text);
    display: flex;
    font-size: var(--dads-font-size-xl);
    font-weight: 700;
    gap: var(--dads-space-2);
    margin-bottom: var(--dads-space-4);
    margin-top: var(--dads-space-6);
}

/* ===== ファイル情報（サイドバー） ===== */
.file-info {
    background: var(--dads-color-surface);
    border: 1px solid var(--dads-color-border);
    border-radius: var(--dads-radius-card);
    margin-top: var(--dads-space-2);
    padding: var(--dads-space-3) var(--dads-space-4);
}
.file-info-name {
    color: var(--dads-color-text);
    font-size: var(--dads-font-size-sm);
    font-weight: 700;
    word-break: break-all;
}
.file-info-size {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
    margin-top: var(--dads-space-1);
}

.text-center { text-align: center; }
.break-all { word-break: break-all; }
.muted-text {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
}
.score-forced {
    color: var(--dads-color-error);
    font-size: var(--dads-font-size-sm);
    font-weight: 700;
    margin-top: var(--dads-space-1);
}
.score-meta {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
    margin-top: var(--dads-space-1);
}
.rule-card-grid {
    align-items: stretch;
    display: grid;
    gap: var(--dads-space-4);
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin-bottom: var(--dads-space-2);
}
.rule-card-body {
    border-radius: var(--dads-radius-card);
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: var(--dads-space-2);
    height: 100%;
    min-height: 128px;
    padding: var(--dads-space-4);
    position: relative;
    width: 100%;
}

/* ===== ルールカードツールチップ ===== */
.rule-card-body[data-tooltip]::after {
    background: var(--dads-color-text);
    border-radius: var(--dads-radius-small);
    bottom: calc(100% + 6px);
    color: var(--dads-color-surface);
    content: attr(data-tooltip);
    font-size: var(--dads-font-size-xs);
    font-weight: 400;
    left: 0;
    line-height: 1.5;
    max-width: 240px;
    opacity: 0;
    padding: var(--dads-space-2) var(--dads-space-3);
    pointer-events: none;
    position: absolute;
    transition: opacity 0.15s ease 0s;
    white-space: pre-wrap;
    width: max-content;
    word-break: break-all;
    z-index: 100;
}
.rule-card-body[data-tooltip]:hover::after {
    opacity: 1;
    transition: opacity 0.15s ease 0.5s;
}
.rule-card-body-pass {
    background: var(--dads-color-surface);
    border: 1px solid var(--dads-color-border);
}
.rule-card-body-fail {
    background: var(--dads-color-error-bg);
}
.rule-card-body-skipped {
    background: var(--dads-color-disabled-bg);
}
.rule-card-body-skipped .rule-id,
.rule-card-body-skipped .rule-message {
    color: var(--dads-color-disabled-text);
}
.rule-id {
    font-size: var(--dads-font-size-sm);
    font-weight: 700;
}
.rule-message {
    font-size: var(--dads-font-size-sm);
    margin-top: var(--dads-space-1);
    color: var(--dads-color-text-muted);
}
@media (max-width: 900px) {
    .rule-card-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
@media (max-width: 640px) {
    .rule-card-grid {
        grid-template-columns: 1fr;
    }
}
.mode-description {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
    margin-top: var(--dads-space-1);
}
.sidebar-score-block {
    margin-top: var(--dads-space-2);
}
.sidebar-score-label {
    color: var(--dads-color-text-muted);
    font-size: var(--dads-font-size-sm);
}
.sidebar-score-value {
    font-size: var(--dads-font-size-xl);
    font-weight: 700;
}
.sidebar-score-missing {
    color: var(--dads-color-disabled-text);
    font-size: var(--dads-font-size-sm);
}
</style>
"""
)


def inject_custom_css() -> None:
    """カスタムCSSを注入する。"""
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, description: str = "") -> None:
    """統一されたページヘッダーを表示する。"""
    st.markdown(
        f'<div class="page-header">'
        f'<span class="page-header-icon">{escape_html(icon)}</span>'
        f'<span class="page-header-title">{escape_html(title)}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if description:
        st.markdown(f'<div class="page-description">{escape_html(description)}</div>', unsafe_allow_html=True)


def section_header(icon: str, title: str) -> None:
    """セクションヘッダーを表示する。"""
    st.markdown(
        f'<div class="section-header">{escape_html(icon)} {escape_html(title)}</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, variant: str = "info") -> str:
    """バッジ用HTMLを返す。variant: pass, fail, info, warn"""
    return f'<span class="badge badge-{escape_html(variant)}">{escape_html(text)}</span>'


def info_card(label: str, value: str) -> str:
    """情報カード用HTMLを返す。"""
    return (
        f'<div class="info-card">'
        f'<div class="info-card-label">{escape_html(label)}</div>'
        f'<div class="info-card-value">{escape_html(value)}</div>'
        f"</div>"
    )


def score_color_class(score: int) -> str:
    """スコアに応じた色クラスサフィックスを返す。"""
    if score >= 90:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "warning"
    return "danger"


def score_bar_color(score: int) -> str:
    """スコアに応じたバーの色を返す。"""
    if score >= 90:
        return token_var("color-success")
    if score >= 70:
        return token_var("color-info")
    if score >= 50:
        return token_var("color-warning")
    return token_var("color-error")
