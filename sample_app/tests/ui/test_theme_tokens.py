"""DADS design token integration tests for the Streamlit UI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harunobu.ui.components.excel_grid import TABLE_COLORS
from harunobu.ui.theme_tokens import (
    COLORS,
    CSS_VARS,
    DADS_CONFIG_THEME,
    DESIGN_TOKENS_COMMIT,
    DESIGN_TOKENS_VERSION,
    RADIUS,
)

_APP_DIR = Path(__file__).resolve().parents[2]
_UI_DIR = _APP_DIR / "harunobu" / "ui"
_CONFIG_PATH = _APP_DIR / ".streamlit" / "config.toml"
_RAW_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{3,8}|rgba?\(")


def _parse_simple_toml(path: Path) -> dict[str, dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
            continue
        if current is None or "=" not in line:
            continue
        key, raw_value = [part.strip() for part in line.split("=", 1)]
        if raw_value.startswith('"') and raw_value.endswith('"'):
            current[key] = raw_value[1:-1]
        else:
            try:
                current[key] = int(raw_value)
            except ValueError:
                current[key] = raw_value
    return sections


def _relative(path: Path) -> str:
    return str(path.relative_to(_APP_DIR))


def _linearized_channel(channel: int) -> float:
    value = channel / 255
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    color = hex_color.removeprefix("#")
    red, green, blue = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linearized_channel(red) + 0.7152 * _linearized_channel(green) + 0.0722 * _linearized_channel(blue)


def _contrast_ratio(foreground: str, background: str) -> float:
    fg_lum = _luminance(foreground)
    bg_lum = _luminance(background)
    lighter, darker = max(fg_lum, bg_lum), min(fg_lum, bg_lum)
    return (lighter + 0.05) / (darker + 0.05)


def test_design_token_source_is_pinned() -> None:
    assert DESIGN_TOKENS_VERSION == "v2.0.1"
    assert DESIGN_TOKENS_COMMIT == "cde7dfe58d53341bba5ebae565406992fbe1218b"


def test_streamlit_theme_matches_dads_tokens() -> None:
    config = _parse_simple_toml(_CONFIG_PATH)
    theme = config["theme"]

    for key, expected in DADS_CONFIG_THEME.items():
        assert theme[key] == expected

    sidebar = config["theme.sidebar"]
    for key in ("backgroundColor", "secondaryBackgroundColor", "textColor", "font", "headingFont", "codeFont"):
        assert sidebar[key] == theme[key]


def test_corner_radius_tokens_match_dads_shape_styles() -> None:
    assert CSS_VARS["radius-card"] == RADIUS["8"]
    assert CSS_VARS["radius-control"] == RADIUS["8"]
    assert CSS_VARS["radius-small"] == RADIUS["8"]
    assert CSS_VARS["radius-medium"] == RADIUS["12"]
    assert CSS_VARS["radius-large"] == RADIUS["16"]
    assert CSS_VARS["radius-badge"] == RADIUS["full"]
    assert DADS_CONFIG_THEME["baseRadius"] == RADIUS["8"]
    assert DADS_CONFIG_THEME["buttonRadius"] == RADIUS["8"]


def test_ui_raw_colors_are_centralized_in_theme_tokens() -> None:
    offenders: list[str] = []
    for path in sorted(_UI_DIR.rglob("*.py")):
        if path.name == "theme_tokens.py":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _RAW_COLOR_RE.search(line):
                offenders.append(f"{_relative(path)}:{line_no}: {line.strip()}")

    assert offenders == []


def test_primary_and_semantic_colors_have_text_contrast() -> None:
    white = COLORS["white"]
    text = COLORS["gray-900"]

    assert _contrast_ratio(COLORS["red-800"], white) >= 4.5
    assert _contrast_ratio(COLORS["red-900"], white) >= 4.5
    assert _contrast_ratio(COLORS["red-500"], white) < 4.5
    assert _contrast_ratio(COLORS["red-50"], text) >= 4.5
    assert _contrast_ratio(COLORS["green-800"], white) >= 4.5
    assert _contrast_ratio(COLORS["orange-800"], white) >= 4.5
    assert _contrast_ratio(COLORS["blue-800"], white) >= 4.5
    assert _contrast_ratio(COLORS["gray-600"], COLORS["gray-100"]) >= 4.5
    assert _contrast_ratio(CSS_VARS["color-button-primary-text"], CSS_VARS["color-button-primary-bg"]) >= 4.5
    assert (
        _contrast_ratio(CSS_VARS["color-button-primary-hover-text"], CSS_VARS["color-button-primary-hover-bg"]) >= 4.5
    )


def test_excel_grid_uses_non_error_table_palette() -> None:
    labels = {color["label"] for color in TABLE_COLORS}
    assert labels == {"blue", "green", "cyan", "purple", "orange"}

    grid_label_pairs = [
        ("blue-800", "blue-50"),
        ("green-800", "green-50"),
        ("cyan-900", "cyan-50"),
        ("purple-800", "purple-50"),
        ("orange-900", "orange-50"),
        ("gray-600", "gray-50"),
    ]
    for foreground, background in grid_label_pairs:
        assert _contrast_ratio(COLORS[foreground], COLORS[background]) >= 4.5
