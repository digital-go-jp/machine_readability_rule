"""Excel grid HTML rendering tests."""

from types import SimpleNamespace

from harunobu.ui.components.excel_grid import build_legend_html, render_detected_grid_html


def test_legend_groups_tables_and_generic_items() -> None:
    legend_html = build_legend_html(
        [
            SimpleNamespace(range="A1:H17"),
            SimpleNamespace(range="B7:H12"),
        ],
        [
            SimpleNamespace(region_type="note"),
            SimpleNamespace(region_type="title"),
        ],
        include_violations=True,
        highlighted_other_types=frozenset({"note", "title"}),
    )

    assert '<div class="grid-legend-section-label">テーブル</div>' in legend_html
    assert '<div class="grid-legend-section-label">汎用</div>' in legend_html
    assert legend_html.count('class="grid-legend-row"') == 2
    assert "グレー文字 = 検出対象外セル" in legend_html
    assert ">note</span>" in legend_html
    assert ">title</span>" in legend_html


def test_hidden_table_highlight_renders_table_cells_neutral() -> None:
    grid_html = render_detected_grid_html(
        {(1, 1): "header"},
        {},
        {
            (1, 1): {
                "bg": "table-header-bg",
                "border": "table-border",
                "tag": "T1",
                "role": "ヘッダー",
                "col_type": "",
                "kind": "table",
            },
        },
        1,
        1,
        show_table_highlight=False,
    )

    assert "table-header-bg" not in grid_html
    assert "table-border" not in grid_html
    assert "T1" not in grid_html
    assert "グレー文字" not in grid_html
    assert "color:var(--dads-color-text);" in grid_html
