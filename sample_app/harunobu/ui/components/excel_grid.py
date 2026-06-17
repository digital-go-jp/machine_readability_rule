"""シート可視化用の共通コンポーネント。

レイアウト検出結果のグリッド描画と、違反セルハイライトを含むHTMLを生成する。
バリデーションページと採点結果ページの両方から再利用される。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from openpyxl.utils.cell import range_boundaries

from harunobu.core.models import Sheet
from harunobu.ui.safe_html import escape_html
from harunobu.ui.theme_tokens import token_var

# 非 A1 形式パターン
_RXCY_RE = re.compile(r"^R(\d+)C(\d+)$")
_ROW_RANGE_JP_RE = re.compile(r"^行(\d+)(?:-(\d+))?$")
_COL_JP_RE = re.compile(r"^列(\d+)$")
_ROW_ONLY_NN_RE = re.compile(r"^(\d+):(\d+)$")

# ─── 色定義 ───

TABLE_COLORS: list[dict[str, str]] = [
    {
        "header": token_var("color-grid-blue-header"),
        "body": token_var("color-grid-blue-body"),
        "border": token_var("color-grid-blue-border"),
        "label": "blue",
    },
    {
        "header": token_var("color-grid-green-header"),
        "body": token_var("color-grid-green-body"),
        "border": token_var("color-grid-green-border"),
        "label": "green",
    },
    {
        "header": token_var("color-grid-cyan-header"),
        "body": token_var("color-grid-cyan-body"),
        "border": token_var("color-grid-cyan-border"),
        "label": "cyan",
    },
    {
        "header": token_var("color-grid-purple-header"),
        "body": token_var("color-grid-purple-body"),
        "border": token_var("color-grid-purple-border"),
        "label": "purple",
    },
    {
        "header": token_var("color-grid-orange-header"),
        "body": token_var("color-grid-orange-body"),
        "border": token_var("color-grid-orange-border"),
        "label": "orange",
    },
]

OTHERS_COLORS: dict[str, dict[str, str]] = {
    "title": {"bg": token_var("color-primary-subtle"), "border": token_var("color-primary")},
    "total": {"bg": token_var("color-warning-bg"), "border": token_var("color-warning")},
    "note": {"bg": token_var("color-grid-note-bg"), "border": token_var("color-grid-note-border")},
    "source": {"bg": token_var("color-surface-subtle"), "border": token_var("color-text-subtle")},
    "isolated": {"bg": token_var("color-disabled-bg"), "border": token_var("color-disabled-text")},
}

TYPE_BADGE_COLOR: dict[str, str] = {
    "text": token_var("color-type-text"),
    "numeric": token_var("color-type-numeric"),
    "date": token_var("color-type-date"),
    "mixed": token_var("color-type-mixed"),
    "empty": token_var("color-type-empty"),
}
DEFAULT_TYPE_BADGE_COLOR = token_var("color-text-muted")

VIOLATION_SEVERITY_COLOR: dict[str, str] = {
    "error": token_var("color-error"),
    "warning": token_var("color-warning-yellow"),
    "info": token_var("color-info"),
}

NOTE_TITLE_REGION_TYPES = frozenset({"note", "title"})

_VIOLATION_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "error": 2}


# ─── データ抽出 ───


def extract_cell_maps(
    sheet: Sheet, max_row: int, max_col: int
) -> tuple[
    dict[tuple[int, int], str],
    dict[tuple[int, int], bool],
    dict[tuple[int, int], bool],
]:
    """Sheet から表示用のセル値・bold・merged マップを抽出する。"""
    cell_values: dict[tuple[int, int], str] = {}
    cell_bold: dict[tuple[int, int], bool] = {}
    cell_merged: dict[tuple[int, int], bool] = {}
    for (r, c), cell in sheet.cells.items():
        if r > max_row or c > max_col:
            continue
        if cell.value is not None:
            cell_values[(r, c)] = str(cell.value)
            cell_bold[(r, c)] = cell.fmt.bold if cell.fmt else False
            cell_merged[(r, c)] = cell.is_merged
    return cell_values, cell_bold, cell_merged


# ─── レイアウト → セルスタイル ───


def build_layout_cell_style(
    tables: Iterable[Any],
    others: Iterable[Any],
    max_row: int,
    max_col: int,
) -> dict[tuple[int, int], dict[str, Any]]:
    """テーブル/Others からセル単位のスタイル辞書を構築する。

    ``tables`` は ``TableRegion`` または ``TableResult`` のいずれでも良い
    （両者とも ``.range`` と ``.layout`` を持つ）。
    """
    cell_style: dict[tuple[int, int], dict[str, Any]] = {}
    for i, table in enumerate(tables):
        colors = TABLE_COLORS[i % len(TABLE_COLORS)]
        sr = table.range.start_row
        sc = table.range.start_col
        er = table.range.end_row
        ec = table.range.end_col
        header_set = set(table.layout.header_rows)
        col_types: dict[int, str] = {ci.col_index: ci.inferred_type for ci in table.layout.columns}
        for r in range(sr, min(er, max_row) + 1):
            for c in range(sc, min(ec, max_col) + 1):
                is_h = r in header_set
                cell_style[(r, c)] = {
                    "bg": colors["header"] if is_h else colors["body"],
                    "border": colors["border"],
                    "tag": f"T{i + 1}",
                    "role": "ヘッダー" if is_h else "ボディ",
                    "col_type": col_types.get(c, ""),
                    "kind": "table",
                }
    for o in others:
        r, c = o.row, o.col
        if r > max_row or c > max_col:
            continue
        rt = o.region_type
        oc = OTHERS_COLORS.get(rt, OTHERS_COLORS["isolated"])
        cell_style[(r, c)] = {
            "bg": oc["bg"],
            "border": oc["border"],
            "tag": rt,
            "role": "",
            "col_type": "",
            "kind": "other",
            "region_type": rt,
        }
    return cell_style


# ─── 違反セルのパース ───


def parse_cell_range(
    cell_range: str,
    table_bounds: tuple[int, int, int, int] | None = None,
) -> list[tuple[int, int]]:
    """セル範囲文字列を ``(row, col)`` のリストに展開する。

    サポートする形式:

    1. ``A1`` / ``A1:C3`` — openpyxl の A1 形式
    2. ``R{row}C{col}`` — 例: ``R3C5``
    3. ``行{n}`` / ``行{n}-{m}`` — 表領域 (``table_bounds``) の全列を展開
    4. ``列{n}`` — 表領域 (``table_bounds``) の全行を展開
    5. ``{n}:{n}`` — 行番号のみ。``table_bounds`` の全列を展開（CSV 系で使用）

    ``table_bounds`` は ``(min_row, min_col, max_row, max_col)``。
    行/列全体指定で ``table_bounds`` が ``None`` の場合や、想定外の表記の
    場合は空リストを返す（呼び出し元で「描画不可」としてカウントできる）。
    """
    if not cell_range:
        return []
    s = cell_range.strip()
    if not s:
        return []

    # 1. A1 形式
    try:
        min_col, min_row, max_col, max_row = range_boundaries(s)
    except (ValueError, TypeError):
        pass
    else:
        if min_row is not None and max_row is not None and min_col is not None and max_col is not None:
            return [(r, c) for r in range(min_row, max_row + 1) for c in range(min_col, max_col + 1)]

    # 2. R{row}C{col}
    m = _RXCY_RE.match(s)
    if m:
        return [(int(m.group(1)), int(m.group(2)))]

    # 3. 行{n} / 行{n}-{m}
    m = _ROW_RANGE_JP_RE.match(s)
    if m:
        if table_bounds is None:
            return []
        _, min_c, _, max_c = table_bounds
        r1 = int(m.group(1))
        r2 = int(m.group(2)) if m.group(2) else r1
        if r1 > r2:
            r1, r2 = r2, r1
        return [(r, c) for r in range(r1, r2 + 1) for c in range(min_c, max_c + 1)]

    # 4. 列{n}
    m = _COL_JP_RE.match(s)
    if m:
        if table_bounds is None:
            return []
        min_r, _, max_r, _ = table_bounds
        c = int(m.group(1))
        return [(r, c) for r in range(min_r, max_r + 1)]

    # 5. {n}:{n}（行番号のみ）
    m = _ROW_ONLY_NN_RE.match(s)
    if m:
        if table_bounds is None:
            return []
        _, min_c, _, max_c = table_bounds
        r1 = int(m.group(1))
        r2 = int(m.group(2))
        if r1 > r2:
            r1, r2 = r2, r1
        return [(r, c) for r in range(r1, r2 + 1) for c in range(min_c, max_c + 1)]

    # 6. 想定外
    return []


def _sheet_bounds_from_meta(sheet_result: Any) -> tuple[int, int, int, int] | None:
    """``SheetResult`` の ``sheet_meta.used_range`` から ``(min_row, min_col, max_row, max_col)`` を得る。

    取得できない場合は ``None`` を返す。
    """
    sheet_meta = getattr(sheet_result, "sheet_meta", None)
    used_range = getattr(sheet_meta, "used_range", "") if sheet_meta else ""
    if not used_range:
        return None
    try:
        min_col, min_row, max_col, max_row = range_boundaries(used_range)
    except (ValueError, TypeError):
        return None
    if min_row is None or max_row is None or min_col is None or max_col is None:
        return None
    return (min_row, min_col, max_row, max_col)


def aggregate_violations_for_sheet(
    sheet_result: Any,
) -> tuple[dict[tuple[int, int], list[dict[str, str]]], int]:
    """``SheetResult`` 配下の ``Violation`` を ``(row, col)`` 単位に集約する。

    戻り値: ``(cell_violations, unrenderable_count)``。

    - ``cell_violations``: ``{(row, col): [{"rule_id", "severity", "description"}, ...]}``
    - ``unrenderable_count``: グリッド上で描画できなかった違反件数（非対応形式・
      表領域情報なしで展開できなかったケース等）。
    """
    out: dict[tuple[int, int], list[dict[str, str]]] = {}
    unrenderable = 0
    sheet_name = sheet_result.sheet_meta.name
    sheet_bounds = _sheet_bounds_from_meta(sheet_result)

    for table in sheet_result.tables:
        tr = table.range
        table_bounds = (tr.start_row, tr.start_col, tr.end_row, tr.end_col)
        for rule_id, check in table.mr_result.all_results().items():
            for v in check.violations:
                if v.sheet and v.sheet != sheet_name:
                    continue
                # まずテーブル範囲で展開を試み、解釈不能なら sheet 範囲で再試行
                cells = parse_cell_range(v.cell_range, table_bounds=table_bounds)
                if not cells and sheet_bounds is not None:
                    cells = parse_cell_range(v.cell_range, table_bounds=sheet_bounds)
                if not cells:
                    unrenderable += 1
                    continue
                for cell in cells:
                    out.setdefault(cell, []).append(
                        {
                            "rule_id": rule_id,
                            "severity": v.severity,
                            "description": v.description,
                        }
                    )
    return out, unrenderable


def _pick_dominant_severity(violations: list[dict[str, str]]) -> str:
    return max(
        (v["severity"] for v in violations),
        key=lambda s: _VIOLATION_SEVERITY_RANK.get(s, 0),
    )


# ─── ユーティリティ ───


def col_letter(col: int) -> str:
    """1 → "A", 27 → "AA" のように列番号を文字に変換する。"""
    result = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(65 + rem) + result
    return result


def _truncate(s: str, max_len: int) -> str:
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def _esc(s: str) -> str:
    return escape_html(s)


def _th_cell(text: str) -> str:
    return (
        f'<td style="text-align:center;padding:4px 8px;color:{token_var("color-text-muted")};'
        f"font-size:12px;font-weight:bold;border-bottom:2px solid {token_var('color-border')};"
        f'background:{token_var("color-surface-subtle")}">{text}</td>'
    )


def _row_num_cell(row: int) -> str:
    return (
        f'<td style="text-align:right;padding:4px 8px;color:{token_var("color-text-muted")};font-size:12px;'
        f'border-right:2px solid {token_var("color-border")};background:{token_var("color-surface-subtle")}">{row}</td>'
    )


# ─── 違反オーバーレイ ───


def _violation_outline_css(violations: list[dict[str, str]]) -> str:
    if not violations:
        return ""
    color = VIOLATION_SEVERITY_COLOR.get(_pick_dominant_severity(violations), token_var("color-error"))
    return f"box-shadow:inset 0 0 0 3px {color};"


def _violation_overlay_html(violations: list[dict[str, str]]) -> str:
    """セル右上に重ねる違反バッジ（rule_id または "+N"）。"""
    if not violations:
        return ""
    color = VIOLATION_SEVERITY_COLOR.get(_pick_dominant_severity(violations), token_var("color-error"))
    if len(violations) == 1:
        label = violations[0]["rule_id"]
    else:
        label = f"{violations[0]['rule_id']}"
    return (
        f'<div style="position:absolute;top:-1px;right:-1px;background:{color};'
        f"color:{token_var('color-surface')};font-size:12px;line-height:1;padding:4px;"
        f"border-radius:0 0 0 {token_var('radius-small')};"
        f'font-weight:bold;white-space:nowrap;pointer-events:none;">{_esc(label)}</div>'
    )


def _is_style_highlighted(
    style: dict[str, Any],
    *,
    show_table_highlight: bool,
    highlighted_other_types: frozenset[str] | set[str] | None,
) -> bool:
    kind = str(style.get("kind", "table"))
    if kind == "table":
        return show_table_highlight
    if kind == "other":
        if highlighted_other_types is None:
            return True
        return str(style.get("region_type", style.get("role", ""))) in highlighted_other_types
    return True


# ─── HTMLレンダリング ───


def render_raw_grid_html(
    cell_values: dict[tuple[int, int], str],
    cell_bold: dict[tuple[int, int], bool],
    cell_merged: dict[tuple[int, int], bool],
    max_row: int,
    max_col: int,
    *,
    violation_cells: dict[tuple[int, int], list[dict[str, str]]] | None = None,
) -> str:
    """元データグリッド（色なし）。違反セルがあれば枠とバッジでハイライト。"""
    vc = violation_cells or {}
    table_style = f"border-collapse:collapse;font-family:{token_var('font-mono')};font-size:12px;white-space:nowrap"
    html: list[str] = [
        '<div style="overflow-x:auto">',
        f'<table style="{table_style}">',
        f'<tr style="background:{token_var("color-surface-subtle")}">',
        _th_cell(""),
    ]
    for c in range(1, max_col + 1):
        html.append(_th_cell(col_letter(c)))
    html.append("</tr>")

    for r in range(1, max_row + 1):
        html.append("<tr>")
        html.append(_row_num_cell(r))
        for c in range(1, max_col + 1):
            val = cell_values.get((r, c), "")
            css = (
                f"padding:4px 8px;border:1px solid {token_var('color-border')};min-width:60px;"
                f"max-width:220px;overflow:hidden;background:{token_var('color-surface')};position:relative;"
            )
            if cell_bold.get((r, c)):
                css += "font-weight:bold;"
            if cell_merged.get((r, c)):
                css += f"color:{token_var('color-info')};"
            vs = vc.get((r, c), [])
            if vs:
                css += _violation_outline_css(vs)
            display = _truncate(val, 24)
            overlay = _violation_overlay_html(vs)
            html.append(f'<td style="{css}">{_esc(display)}{overlay}</td>')
        html.append("</tr>")

    html.append("</table></div>")
    return "".join(html)


def render_detected_grid_html(
    cell_values: dict[tuple[int, int], str],
    cell_bold: dict[tuple[int, int], bool],
    cell_style: dict[tuple[int, int], dict[str, Any]],
    max_row: int,
    max_col: int,
    *,
    violation_cells: dict[tuple[int, int], list[dict[str, str]]] | None = None,
    show_table_highlight: bool = True,
    highlighted_other_types: frozenset[str] | set[str] | None = None,
) -> str:
    """レイアウト色付きグリッド。違反セルがあれば枠とバッジで重ねる。"""
    vc = violation_cells or {}
    table_style = f"border-collapse:collapse;font-family:{token_var('font-mono')};font-size:12px;white-space:nowrap"
    html: list[str] = [
        '<div style="overflow-x:auto">',
        f'<table style="{table_style}">',
        f'<tr style="background:{token_var("color-surface-subtle")}">',
        _th_cell(""),
    ]
    for c in range(1, max_col + 1):
        html.append(_th_cell(col_letter(c)))
    html.append("</tr>")

    for r in range(1, max_row + 1):
        html.append("<tr>")
        html.append(_row_num_cell(r))
        for c in range(1, max_col + 1):
            val = cell_values.get((r, c), "")
            style = cell_style.get((r, c))
            vs = vc.get((r, c), [])
            is_highlighted = bool(style) and _is_style_highlighted(
                style,
                show_table_highlight=show_table_highlight,
                highlighted_other_types=highlighted_other_types,
            )
            display = _truncate(val, 20)
            tag_html = ""

            if style and is_highlighted:
                bg = style["bg"]
                bdr = style["border"]
                tag = style["tag"]
                role = style["role"]
                col_type = style["col_type"]
                css = (
                    f"padding:4px;border:2px solid {bdr};min-width:60px;"
                    f"max-width:220px;overflow:hidden;background:{bg};position:relative;"
                )
                type_str = f" [{col_type}]" if col_type else ""
                tag_html = (
                    f'<div style="font-size:12px;color:{bdr};text-align:right;'
                    f'line-height:1;margin-top:4px">{_esc(str(tag))} {_esc(str(role))}{_esc(type_str)}</div>'
                )
            elif style:
                css = (
                    f"padding:4px 8px;border:1px solid {token_var('color-border-subtle')};min-width:60px;"
                    f"max-width:220px;overflow:hidden;background:{token_var('color-surface')};"
                    f"color:{token_var('color-text')};position:relative;"
                )
            else:
                text_color = token_var("color-text-subtle") if vs else token_var("color-grid-excluded")
                css = (
                    f"padding:4px 8px;border:1px solid {token_var('color-border-subtle')};min-width:60px;"
                    f"max-width:220px;overflow:hidden;background:{token_var('color-grid-excluded-bg')};"
                    f"color:{text_color};position:relative;"
                )
            if cell_bold.get((r, c)):
                css += "font-weight:bold;"
            if vs:
                css += _violation_outline_css(vs)
            overlay = _violation_overlay_html(vs)
            html.append(f'<td style="{css}">{_esc(display)}{tag_html}{overlay}</td>')
        html.append("</tr>")

    html.append("</table></div>")
    return "".join(html)


def build_legend_html(
    tables: Iterable[Any],
    others: Iterable[Any],
    *,
    include_violations: bool = False,
    show_tables: bool = True,
    highlighted_other_types: frozenset[str] | set[str] | None = None,
) -> str:
    """凡例HTMLを返す。"""
    parts: list[str] = ['<div class="grid-legend">', '<div class="grid-legend-title">凡例</div>']

    table_items = list(tables)
    if show_tables and table_items:
        parts.append(
            '<div class="grid-legend-section">'
            '<div class="grid-legend-section-label">テーブル</div>'
            '<div class="grid-legend-table-list">'
        )
        for i, table in enumerate(table_items):
            c = TABLE_COLORS[i % len(TABLE_COLORS)]
            parts.append(
                '<div class="grid-legend-row">'
                f'<span class="grid-legend-range"><b>T{i + 1}</b>: {_esc(str(table.range))}</span>'
                f'<span class="grid-legend-chip" style="background:{c["header"]};border-color:{c["border"]};">'
                "ヘッダー</span>"
                f'<span class="grid-legend-chip" style="background:{c["body"]};border-color:{c["border"]};">'
                "ボディ</span>"
                "</div>"
            )
        parts.append("</div></div>")

    seen: set[str] = set()
    other_items: list[str] = []
    for o in others:
        rt = o.region_type
        if rt not in seen and (highlighted_other_types is None or rt in highlighted_other_types):
            seen.add(rt)
            oc = OTHERS_COLORS.get(rt, OTHERS_COLORS["isolated"])
            other_items.append(
                f'<span class="grid-legend-chip" style="background:{oc["bg"]};border-color:{oc["border"]};">'
                f"{_esc(str(rt))}</span>"
            )

    parts.append(
        '<div class="grid-legend-section">'
        '<div class="grid-legend-section-label">汎用</div>'
        '<div class="grid-legend-generic-list">'
        '<span class="grid-legend-muted-text">グレー文字 = 検出対象外セル</span>'
    )

    parts.extend(other_items)

    if include_violations:
        for sev, color in VIOLATION_SEVERITY_COLOR.items():
            parts.append(
                '<span class="grid-legend-violation-item">'
                f'<span class="grid-legend-violation-swatch" style="border-color:{color};"></span>'
                f"<span>{_esc(sev)}</span></span>"
            )
        parts.append("</span>")

    parts.append("</div></div></div>")
    return "".join(parts)
