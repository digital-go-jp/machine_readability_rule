"""UI HTML escaping helpers のテスト。"""

from harunobu.ui.components.excel_grid import render_raw_grid_html
from harunobu.ui.safe_html import escape_html


def test_escape_html_escapes_quotes_and_tags() -> None:
    """タグと引用符を HTML として解釈されない形にする。"""
    assert escape_html('<img src=x onerror="alert(1)">') == "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;"


def test_raw_grid_html_escapes_cell_values_and_violation_badges() -> None:
    """Excel 由来のセル値と違反バッジの rule_id をエスケープする。"""
    grid_html = render_raw_grid_html(
        {(1, 1): '<b title="x">v</b>'},
        {},
        {},
        1,
        1,
        violation_cells={(1, 1): [{"rule_id": 'R" <x>', "severity": "error", "description": ""}]},
    )

    assert '<b title="x">' not in grid_html
    assert 'R" <x>' not in grid_html
    assert "&lt;b title=&quot;x&quot;&gt;v&lt;/b&gt;" in grid_html
    assert "R&quot; &lt;x&gt;" in grid_html
