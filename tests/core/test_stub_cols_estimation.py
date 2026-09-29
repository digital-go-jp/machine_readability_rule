"""stub_cols 推定のテスト"""

from __future__ import annotations

from harunobu.core.layout.island import (
    _estimate_stub_cols,
    _is_code_like_integers,
)
from harunobu.core.models import (
    Cell,
    CellFormat,
    CellPosition,
    ColumnSchema,
    Sheet,
)


def _make_sheet(
    rows_data: list[list],
    *,
    bg_colors: dict[tuple[int, int], str] | None = None,
    border_rights: dict[tuple[int, int], str] | None = None,
    border_lefts: dict[tuple[int, int], str] | None = None,
    bold_cells: set[tuple[int, int]] | None = None,
) -> Sheet:
    """テスト用シートを生成するヘルパー。

    rows_data: 行データ（1-indexed で格納）
    bg_colors: (row, col) → カラーコード文字列（例: "FFFF0000"）
    border_rights: (row, col) → 罫線スタイル文字列（例: "thin"）
    border_lefts: (row, col) → 罫線スタイル文字列（例: "thin"）
    bold_cells: 太字にする (row, col) のセット
    """
    cells: dict[tuple[int, int], Cell] = {}
    max_row = len(rows_data)
    max_col = max((len(row) for row in rows_data), default=0)

    for r_idx, row in enumerate(rows_data, start=1):
        for c_idx, value in enumerate(row, start=1):
            fmt = CellFormat(
                bold=(bold_cells is not None and (r_idx, c_idx) in bold_cells),
                bg_color=(bg_colors or {}).get((r_idx, c_idx)),
                border_right=(border_rights or {}).get((r_idx, c_idx)),
                border_left=(border_lefts or {}).get((r_idx, c_idx)),
            )
            cells[(r_idx, c_idx)] = Cell(
                pos=CellPosition(row=r_idx, col=c_idx),
                value=value,
                fmt=fmt,
            )

    return Sheet(
        name="TestSheet",
        cells=cells,
        merged_cells=[],
        max_row=max_row,
        max_col=max_col,
    )


def _schemas(*pairs: tuple[int, str]) -> list[ColumnSchema]:
    """(col_index, inferred_type) のペアから ColumnSchema リストを作る。"""
    return [ColumnSchema(col_index=c, inferred_type=t) for c, t in pairs]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _is_code_like_integers 単体テスト
# ---------------------------------------------------------------------------


class TestIsCodeLikeIntegers:
    def test_c1_sequential(self):
        assert _is_code_like_integers([1, 2, 3, 4, 5]) is True

    def test_c2_large_ids(self):
        assert _is_code_like_integers([1001, 1002, 1003]) is True

    def test_c3_step_sequence(self):
        assert _is_code_like_integers([10, 20, 30]) is True

    def test_c4_reverse_order(self):
        assert _is_code_like_integers([5, 3, 1]) is True

    def test_c5_unordered_unique(self):
        assert _is_code_like_integers([1, 3, 2]) is True

    def test_c6_duplicates(self):
        assert _is_code_like_integers([1, 2, 2, 3]) is False

    def test_c7_contains_zero(self):
        assert _is_code_like_integers([0, 1, 2]) is False

    def test_c8_floats_with_decimal(self):
        assert _is_code_like_integers([1.5, 2.5, 3.5]) is False

    def test_c9_single_element(self):
        assert _is_code_like_integers([1]) is False

    def test_c10_strings(self):
        assert _is_code_like_integers(["A", "B"]) is False

    def test_c11_zero_padded_strings(self):
        assert _is_code_like_integers(["001", "002", "003"]) is True

    def test_c12_long_zero_padded_strings(self):
        assert _is_code_like_integers(["00101", "00102", "00103"]) is True

    def test_c13_zero_padded_duplicates(self):
        assert _is_code_like_integers(["001", "001", "003"]) is False

    def test_c14_zero_padded_contains_zero(self):
        assert _is_code_like_integers(["0", "001", "002"]) is False

    def test_c15_mixed_int_and_str(self):
        assert _is_code_like_integers([1, "002", 3]) is True


# ---------------------------------------------------------------------------
# _estimate_stub_cols 統合テスト
#
# シート構成: 行1=ヘッダー、行2-6=ボディ（5行）
# start_col=1, end_col=列数
# ---------------------------------------------------------------------------

HEADER_ROW = 1
BODY_START = 2
BODY_END = 6  # 5行ボディ

# 全ボディ行・col 1 に bg_color を設定するヘルパー
_BG = "FFAABBCC"
_BORDER = "thin"


def _bg_col1() -> dict[tuple[int, int], str]:
    return {(r, 1): _BG for r in range(BODY_START, BODY_END + 1)}


def _border_col1_only() -> dict[tuple[int, int], str]:
    """col 1 のみ border_right（col 2 以降なし）"""
    return {(r, 1): _BORDER for r in range(BODY_START, BODY_END + 1)}


def _border_left_col2_only() -> dict[tuple[int, int], str]:
    """col 2 のみ border_left（col 1 の border_right なし）"""
    return {(r, 2): _BORDER for r in range(BODY_START, BODY_END + 1)}


def _border_all_cols(n_cols: int) -> dict[tuple[int, int], str]:
    """全列に均一な border_right"""
    result = {}
    for c in range(1, n_cols + 1):
        for r in range(BODY_START, BODY_END + 1):
            result[(r, c)] = _BORDER
    return result


def _bold_col1() -> set[tuple[int, int]]:
    return {(r, 1) for r in range(BODY_START, BODY_END + 1)}


class TestEstimateStubCols:
    def test_1_text_plus_numeric(self):
        """text 1列 + numeric 3列 → 先頭列が stub"""
        rows = [["ラベル", 10, 20, 30]] + [["A", 1, 2, 3]] * 5
        sheet = _make_sheet(rows)
        cols = _schemas((1, "text"), (2, "numeric"), (3, "numeric"), (4, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 4, cols) == [1]

    def test_2_text_with_bg(self):
        """text 1列（背景色あり）+ numeric 3列 → 先頭列が stub"""
        rows = [["ラベル", 10, 20, 30]] + [["A", 1, 2, 3]] * 5
        sheet = _make_sheet(rows, bg_colors=_bg_col1())
        cols = _schemas((1, "text"), (2, "numeric"), (3, "numeric"), (4, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 4, cols) == [1]

    def test_3_text_with_border_right_only(self):
        """text 1列（右罫線あり、隣列なし）+ numeric 3列 → 先頭列が stub"""
        rows = [["ラベル", 10, 20, 30]] + [["A", 1, 2, 3]] * 5
        sheet = _make_sheet(rows, border_rights=_border_col1_only())
        cols = _schemas((1, "text"), (2, "numeric"), (3, "numeric"), (4, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 4, cols) == [1]

    def test_4_text_with_uniform_border(self):
        """text 1列（全列均一罫線）+ numeric 3列 → 型スコアのみで stub"""
        rows = [["ラベル", 10, 20, 30]] + [["A", 1, 2, 3]] * 5
        sheet = _make_sheet(rows, border_rights=_border_all_cols(4))
        cols = _schemas((1, "text"), (2, "numeric"), (3, "numeric"), (4, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 4, cols) == [1]

    def test_5_two_text_cols(self):
        """text 2列 + numeric 3列 → 先頭2列が stub"""
        rows = [["区分", "ラベル", 10, 20, 30]] + [["A", "B", 1, 2, 3]] * 5
        sheet = _make_sheet(rows)
        cols = _schemas((1, "text"), (2, "text"), (3, "numeric"), (4, "numeric"), (5, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 5, cols) == [1, 2]

    def test_6_numeric_only(self):
        """全列 numeric（非コード値）→ stub なし"""
        rows = [["A", "B", "C"]] + [[10, 10, 10]] * 5  # 重複値 → not code-like
        sheet = _make_sheet(rows)
        cols = _schemas((1, "numeric"), (2, "numeric"), (3, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 3, cols) == []

    def test_7_date_plus_numeric(self):
        """date 列 + numeric 列 → stub なし"""
        rows = [["日付", "値"]] + [["2020-01-01", 100]] * 5
        sheet = _make_sheet(rows)
        cols = _schemas((1, "date"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == []

    def test_8_mixed_no_format(self):
        """mixed（書式なし）+ numeric → stub なし"""
        rows = [["区分", "値"]] + [["A", 1]] * 5
        sheet = _make_sheet(rows)
        cols = _schemas((1, "mixed"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == []

    def test_9_mixed_uniform_border(self):
        """mixed（全列均一罫線）+ numeric → border差分=0、stub なし"""
        rows = [["区分", "値"]] + [["A", 1]] * 5
        sheet = _make_sheet(rows, border_rights=_border_all_cols(2))
        cols = _schemas((1, "mixed"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == []

    def test_10_mixed_with_border_diff(self):
        """mixed（右罫線あり、隣列なし）+ numeric → 差分スコア+2でstub"""
        rows = [["区分", "値"]] + [["A", 1]] * 5
        sheet = _make_sheet(rows, border_rights=_border_col1_only())
        cols = _schemas((1, "mixed"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_11_mixed_with_bg(self):
        """mixed（背景色あり）+ numeric → stub"""
        rows = [["区分", "値"]] + [["A", 1]] * 5
        sheet = _make_sheet(rows, bg_colors=_bg_col1())
        cols = _schemas((1, "mixed"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_12_code_like_no_format(self):
        """連番整数（書式なし）+ numeric → 型スコア0、stub なし"""
        rows = [["No", "値"]] + [[i, i * 10] for i in range(1, 6)]
        sheet = _make_sheet(rows)
        cols = _schemas((1, "numeric"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == []

    def test_13_code_like_with_bg(self):
        """連番整数（背景色あり）+ numeric → 0+2=2 でstub"""
        rows = [["No", "値"]] + [[i, i * 10] for i in range(1, 6)]
        sheet = _make_sheet(rows, bg_colors=_bg_col1())
        cols = _schemas((1, "numeric"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_14_code_like_with_border_diff(self):
        """連番整数（右罫線差分あり）+ numeric → 0+2=2 でstub"""
        rows = [["No", "値"]] + [[i, i * 10] for i in range(1, 6)]
        sheet = _make_sheet(rows, border_rights=_border_col1_only())
        cols = _schemas((1, "numeric"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_15_max_stub_limit(self):
        """text 4列 → MAX=3 の上限で先頭3列のみ stub"""
        rows = [["A", "B", "C", "D", "値"]] + [["a", "b", "c", "d", 1]] * 5
        sheet = _make_sheet(rows)
        cols = _schemas((1, "text"), (2, "text"), (3, "text"), (4, "text"), (5, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 5, cols) == [1, 2, 3]

    def test_16_text_then_mixed_no_format(self):
        """text 1列 + mixed（書式なし）+ numeric → 1列目のみ stub（2列目はスコア不足）"""
        rows = [["ラベル", "区分", "値"]] + [["A", "x", 1]] * 5
        sheet = _make_sheet(rows)
        cols = _schemas((1, "text"), (2, "mixed"), (3, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 3, cols) == [1]

    def test_17_single_column(self):
        """列数1 → max_stubs=0 で常に空"""
        rows = [["値"]] + [[i] for i in range(1, 6)]
        sheet = _make_sheet(rows)
        cols = _schemas((1, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 1, cols) == []

    def test_18_no_body_rows_text_col(self):
        """ボディ行数0、text列 + numeric列 → 書式スコアなし、型スコア+2のみで stub"""
        rows = [["ラベル", "値"]]
        sheet = _make_sheet(rows)
        cols = _schemas((1, "text"), (2, "numeric"))
        # body_start > body_end の状態
        assert _estimate_stub_cols(sheet, 2, 1, 1, 2, cols) == [1]

    def test_19_zero_padded_str_no_format(self):
        """ゼロパディング文字列ID列（書式なし）→ 型スコア0、stub なし"""
        rows = [["No", "値"]] + [[f"{i:03d}", i * 10] for i in range(1, 6)]
        sheet = _make_sheet(rows)
        cols = _schemas((1, "numeric"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == []

    def test_20_zero_padded_str_with_bg(self):
        """ゼロパディング文字列ID列（背景色あり）→ 0+2=2 でstub"""
        rows = [["No", "値"]] + [[f"{i:03d}", i * 10] for i in range(1, 6)]
        sheet = _make_sheet(rows, bg_colors=_bg_col1())
        cols = _schemas((1, "numeric"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_21_zero_padded_str_with_border_diff(self):
        """ゼロパディング文字列ID列（右罫線差分あり）→ 0+2=2 でstub"""
        rows = [["No", "値"]] + [[f"{i:03d}", i * 10] for i in range(1, 6)]
        sheet = _make_sheet(rows, border_rights=_border_col1_only())
        cols = _schemas((1, "numeric"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_22_no_col_skipped_text_col_detected(self):
        """No.列（code-like、書式なし）+ text列 + numeric列 → No.を飛ばしてtext列をstub判定"""
        prefs = ["北海道", "青森県", "岩手県", "秋田県", "宮城県"]
        pops = [1234567, 234566, 345677, 456788, 567899]
        rows = [["No.", "都道府県", "人口"]] + [[i + 1, prefs[i], pops[i]] for i in range(5)]
        sheet = _make_sheet(rows)
        cols = _schemas((1, "numeric"), (2, "text"), (3, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 3, cols) == [2]

    def test_23_no_col_and_text_col_both_in_range(self):
        """No.列 + text列（いずれも3列上限内）→ text列のみ stub"""
        rows = [["No.", "区分", "値1", "値2"]] + [[i + 1, f"区{i}", i * 10, i * 100] for i in range(5)]
        sheet = _make_sheet(rows)
        cols = _schemas((1, "numeric"), (2, "text"), (3, "numeric"), (4, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 4, cols) == [2]

    def test_24_border_as_left_of_adjacent_text(self):
        """混合列（書式なし）+ numeric: 境界罫線が col 2 の border_left として定義 → stub"""
        rows = [["区分", "値"]] + [["A", 1]] * 5
        sheet = _make_sheet(rows, border_lefts=_border_left_col2_only())
        cols = _schemas((1, "mixed"), (2, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 2, cols) == [1]

    def test_25_border_left_uniform_no_diff(self):
        """col2・col3 の border_left が均一 → 差分 0 → stub なし。

        col1 の border_left はテーブル外縁を表すため境界判定に影響しない。
        """
        rows = [["区分", "値1", "値2"]] + [["A", 1, 2]] * 5
        # col1-col2 境界（col2.border_left）と col2-col3 境界（col3.border_left）が均一
        sheet = _make_sheet(
            rows, border_lefts={(r, c): _BORDER for r in range(BODY_START, BODY_END + 1) for c in (2, 3)}
        )
        cols = _schemas((1, "mixed"), (2, "numeric"), (3, "numeric"))
        assert _estimate_stub_cols(sheet, BODY_START, BODY_END, 1, 3, cols) == []
