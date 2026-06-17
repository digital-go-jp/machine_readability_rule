"""IslandDetector — 非空セルの連結領域からテーブルを検出する

シート上の非空セルの「島」（連結矩形領域）を検出し、
TableRegion のリストとして返す。lite モードのデフォルト検出器。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from typing import Literal

from harunobu.core.models import (
    CellRange,
    ColumnHeader,
    ColumnSchema,
    DetectionResult,
    OtherCell,
    Sheet,
    TableLayout,
    TableRegion,
)

logger = logging.getLogger(__name__)

# 空行/空列がこの数以上続いたら島の境界とみなす
_GAP_THRESHOLD = 1

# ヘッダーとして検出する最大連続行数（結合セルスパンで動的拡張される）
_MAX_HEADER_ROWS = 5

# ヘッダー・ボディ間の空行統合で許容する最大ギャップ行数
_HEADER_BODY_GAP_TOLERANCE = 1

# 数値文字列パターン（CSV対応）
_NUMERIC_STR_PATTERNS = [
    re.compile(r"^[+-]?\d+$"),
    re.compile(r"^[+-]?\d+\.\d+$"),
    re.compile(r"^[+-]?\d{1,3}(,\d{3})*(\.\d+)?$"),
]

# 合計行キーワード（末尾トリミング用）
_TOTAL_KEYWORDS = re.compile(r"^(合計|小計|総計|計|総数|総合計|3カ年平均)$")

# 欠損値プレースホルダー（列型推定時にemptyとして扱う）
_MISSING_PLACEHOLDERS = frozenset({"-", "－", "–", "―", "…", "‥", "*", "×", "x", "X", "N/A", "n/a", "NA", "-\u3000"})

# 行ヘッダー（stub_cols）推定
_MAX_STUB_COLS = 3
_STUB_SCORE_THRESHOLD = 2
_STUB_FMT_RATE_THRESHOLD = 0.8  # 背景色・太字・罫線差分の採用率閾値
_NO_BG_COLORS: frozenset[str] = frozenset({"FFFFFFFF"})


class IslandDetector:
    """非空セル領域の島検出を行う。"""

    def __init__(
        self,
        gap_threshold: int = _GAP_THRESHOLD,
        max_header_rows: int = _MAX_HEADER_ROWS,
    ) -> None:
        self.gap_threshold = gap_threshold
        self.max_header_rows = max_header_rows

    def detect(self, sheet: Sheet) -> list[TableRegion]:
        """シート内のテーブル領域を検出する。

        Args:
            sheet (Sheet): 対象シート

        Returns:
            list[TableRegion]: 検出されたテーブル領域のリスト
        """
        return self.detect_with_others(sheet).tables

    def detect_with_others(self, sheet: Sheet) -> DetectionResult:
        """シート内のテーブル領域と非テーブルセルを検出する。

        Args:
            sheet (Sheet): 対象シート

        Returns:
            DetectionResult: テーブル領域と非テーブルセルのリスト
        """
        if not sheet.cells or sheet.max_row == 0 or sheet.max_col == 0:
            return DetectionResult()

        # 非空セルのある行・列を特定
        occupied_rows: set[int] = set()
        occupied_cols: set[int] = set()
        for (r, c), cell in sheet.cells.items():
            if cell.value is not None:
                occupied_rows.add(r)
                occupied_cols.add(c)

        if not occupied_rows or not occupied_cols:
            return DetectionResult()

        # 行方向の連続領域を分割
        row_bands = _split_into_bands(sorted(occupied_rows), self.gap_threshold)
        col_bands = _split_into_bands(sorted(occupied_cols), self.gap_threshold)

        # ヘッダー・ボディ間の空行で分割されたバンドを統合
        row_bands = _merge_header_body_bands(sheet, row_bands, col_bands, _HEADER_BODY_GAP_TOLERANCE)

        # 各行バンド×列バンドの交差を島候補にする
        candidates: list[TableRegion] = []
        all_others: list[OtherCell] = []
        for row_band in row_bands:
            for col_band in col_bands:
                region, others = self._evaluate_region_with_trim(sheet, row_band, col_band)
                if region is not None:
                    candidates.append(region)
                all_others.extend(others)

        # 小さすぎる島は除外 → others に変換
        tables: list[TableRegion] = []
        for r in candidates:
            if self._is_trivial(r):
                # 領域内の全セルを others に変換
                for row in range(r.range.start_row, r.range.end_row + 1):
                    for col in range(r.range.start_col, r.range.end_col + 1):
                        cell = sheet.get_cell(row, col)
                        if cell and cell.value is not None:
                            all_others.append(
                                OtherCell(
                                    row=row,
                                    col=col,
                                    value=cell.value,
                                    region_type="isolated",
                                )
                            )
            else:
                tables.append(r)

        # 列方向に隣接する同構造テーブルを統合
        tables = self._merge_column_adjacent_regions(sheet, tables)

        # フォーム型レイアウト: 同一行範囲の狭いテーブル群を統合
        tables = self._merge_form_fragments(sheet, tables)

        # ヘッダーなしテーブルに直上テーブルのヘッダーを継承
        tables = self._inherit_headers_from_above(sheet, tables)

        logger.debug("IslandDetector: %d 領域を検出 (sheet=%s)", len(tables), sheet.name)
        return DetectionResult(tables=tables, others=all_others)

    def _evaluate_region(
        self,
        sheet: Sheet,
        row_band: tuple[int, int],
        col_band: tuple[int, int],
    ) -> TableRegion | None:
        """行バンドと列バンドの交差領域を評価する。"""
        region, _ = self._evaluate_region_with_trim(sheet, row_band, col_band)
        return region

    def _evaluate_region_with_trim(
        self,
        sheet: Sheet,
        row_band: tuple[int, int],
        col_band: tuple[int, int],
    ) -> tuple[TableRegion | None, list[OtherCell]]:
        """行バンドと列バンドの交差領域を評価し、トリミングを行う。"""
        start_row, end_row = row_band
        start_col, end_col = col_band

        # 領域内に非空セルがあるか確認
        non_empty_count = 0
        for r in range(start_row, end_row + 1):
            for c in range(start_col, end_col + 1):
                cell = sheet.get_cell(r, c)
                if cell and cell.value is not None:
                    non_empty_count += 1

        if non_empty_count == 0:
            return None, []

        # 境界トリミング
        trimmed_start, trimmed_end, others = _trim_boundaries(sheet, start_row, end_row, start_col, end_col)

        # トリミング後に有効な行がなくなった場合
        if trimmed_start > trimmed_end:
            return None, others

        # トリミング後の充填率と行充填率から信頼度を算出
        trimmed_rows = trimmed_end - trimmed_start + 1
        table_width = end_col - start_col + 1
        trimmed_total = trimmed_rows * table_width
        trimmed_non_empty = 0
        rows_with_data = 0
        for r in range(trimmed_start, trimmed_end + 1):
            row_filled = 0
            for c in range(start_col, end_col + 1):
                cell = sheet.get_cell(r, c)
                if cell and cell.value is not None:
                    row_filled += 1
            trimmed_non_empty += row_filled
            if row_filled >= max(min(table_width * 0.3, 2), 1):
                rows_with_data += 1

        fill_rate = trimmed_non_empty / trimmed_total if trimmed_total > 0 else 0.0
        row_fill_rate = rows_with_data / trimmed_rows if trimmed_rows > 0 else 0.0
        # セル充填率と行充填率の加重平均（幅広テーブルで行充填率を重視）
        confidence = min(fill_rate * 0.6 + row_fill_rate * 0.6, 1.0)

        # レイアウト推定
        layout = _estimate_layout(sheet, trimmed_start, trimmed_end, start_col, end_col, self.max_header_rows)

        region = TableRegion(
            range=CellRange(
                start_row=trimmed_start,
                start_col=start_col,
                end_row=trimmed_end,
                end_col=end_col,
            ),
            layout=layout,
            confidence=round(confidence, 3),
        )
        return region, others

    def _is_trivial(self, region: TableRegion) -> bool:
        """テーブルとみなすには小さすぎる領域を判定する。

        除外条件:
        - 1セルのみ
        - 1列のみ（フォームのラベル列など）
        """
        r = region.range
        if r.start_row == r.end_row and r.start_col == r.end_col:
            return True
        if r.start_col == r.end_col:
            return True
        return False

    def _merge_column_adjacent_regions(self, sheet: Sheet, tables: list[TableRegion]) -> list[TableRegion]:
        """行範囲が同一で列方向に隣接するテーブルを統合する。"""
        if len(tables) <= 1:
            return tables

        sorted_tables = sorted(tables, key=lambda t: (t.range.start_row, t.range.start_col))
        merged: list[TableRegion] = []
        skip: set[int] = set()

        for i, left in enumerate(sorted_tables):
            if i in skip:
                continue
            current = left
            for j in range(i + 1, len(sorted_tables)):
                if j in skip:
                    continue
                right = sorted_tables[j]

                # 行範囲の互換性チェック（完全一致 or ±1行差で重なりが大きい）
                row_diff_start = abs(current.range.start_row - right.range.start_row)
                row_diff_end = abs(current.range.end_row - right.range.end_row)
                if row_diff_start > 1 or row_diff_end > 1:
                    continue
                # 列隣接チェック（ギャップが gap_threshold 以下）
                col_gap = right.range.start_col - current.range.end_col - 1
                if col_gap < 1 or col_gap > self.gap_threshold:
                    continue
                # ヘッダー行の互換性チェック（一致、または一方が他方の部分集合）
                h_left = set(current.layout.header_rows)
                h_right = set(right.layout.header_rows)
                if h_left != h_right and not h_left.issubset(h_right) and not h_right.issubset(h_left):
                    continue

                # 統合: 行範囲はunion、列範囲は拡張
                new_start_row = min(current.range.start_row, right.range.start_row)
                new_end_row = max(current.range.end_row, right.range.end_row)
                new_start_col = current.range.start_col
                new_end_col = right.range.end_col
                layout = _estimate_layout(
                    sheet,
                    new_start_row,
                    new_end_row,
                    new_start_col,
                    new_end_col,
                    self.max_header_rows,
                )
                # 充填率再計算
                table_rows = new_end_row - new_start_row + 1
                table_width = new_end_col - new_start_col + 1
                total = table_rows * table_width
                non_empty = 0
                rows_with_data = 0
                for r in range(new_start_row, new_end_row + 1):
                    row_filled = sum(
                        1
                        for c in range(new_start_col, new_end_col + 1)
                        if (cell := sheet.get_cell(r, c)) and cell.value is not None
                    )
                    non_empty += row_filled
                    if row_filled >= max(min(table_width * 0.3, 2), 1):
                        rows_with_data += 1
                fill_rate = non_empty / total if total > 0 else 0.0
                row_fill_rate = rows_with_data / table_rows if table_rows > 0 else 0.0
                confidence = round(min(fill_rate * 0.6 + row_fill_rate * 0.6, 1.0), 3)

                current = TableRegion(
                    range=CellRange(
                        start_row=new_start_row,
                        start_col=new_start_col,
                        end_row=new_end_row,
                        end_col=new_end_col,
                    ),
                    layout=layout,
                    confidence=confidence,
                )
                skip.add(j)
            merged.append(current)
        return merged

    def _merge_form_fragments(self, sheet: Sheet, tables: list[TableRegion]) -> list[TableRegion]:
        """同一行範囲の狭いテーブル群をフォーム型として統合する。

        行政帳票では、1つの論理テーブルが列方向に大きなギャップを持ち、
        多数の1-2列テーブルに分割されることがある。
        行範囲が大きく重なる3つ以上の狭いテーブル（幅3列以下）がある場合、
        それらを1つのテーブルに統合する。
        """
        if len(tables) <= 2:
            return tables

        # 行範囲の重なりでグルーピング（80%以上重なるテーブルを同一グループに）
        row_range_groups: dict[int, list[int]] = {}  # group_id -> table indices
        group_id = 0
        assigned: dict[int, int] = {}  # table_idx -> group_id

        for i, t in enumerate(tables):
            if i in assigned:
                continue
            group = [i]
            assigned[i] = group_id
            for j in range(i + 1, len(tables)):
                if j in assigned:
                    continue
                # 行範囲の重なり率を計算
                overlap_start = max(t.range.start_row, tables[j].range.start_row)
                overlap_end = min(t.range.end_row, tables[j].range.end_row)
                if overlap_start > overlap_end:
                    continue
                overlap = overlap_end - overlap_start + 1
                len_i = t.range.end_row - t.range.start_row + 1
                len_j = tables[j].range.end_row - tables[j].range.start_row + 1
                ratio = overlap / min(len_i, len_j)
                if ratio >= 0.8:
                    group.append(j)
                    assigned[j] = group_id
            row_range_groups[group_id] = group
            group_id += 1

        merged_indices: set[int] = set()
        new_tables: list[TableRegion] = []

        for gid, indices in row_range_groups.items():
            if len(indices) < 3:
                continue
            # 狭いテーブル（幅3列以下）をカウント
            narrow = [i for i in indices if tables[i].range.end_col - tables[i].range.start_col + 1 <= 3]
            if len(narrow) < 3:
                continue

            # 統合対象: 同グループの全テーブル（狭くなくても含める）
            merge_targets = indices
            start_row = min(tables[i].range.start_row for i in merge_targets)
            end_row = max(tables[i].range.end_row for i in merge_targets)
            all_start_col = min(tables[i].range.start_col for i in merge_targets)
            all_end_col = max(tables[i].range.end_col for i in merge_targets)

            # 統合後のレイアウト推定
            layout = _estimate_layout(
                sheet,
                start_row,
                end_row,
                all_start_col,
                all_end_col,
                self.max_header_rows,
            )

            # 信頼度再計算
            table_rows = end_row - start_row + 1
            table_width = all_end_col - all_start_col + 1
            total_cells = table_rows * table_width
            non_empty = 0
            rows_with_data = 0
            for r in range(start_row, end_row + 1):
                row_filled = 0
                for c in range(all_start_col, all_end_col + 1):
                    cell = sheet.get_cell(r, c)
                    if cell and cell.value is not None:
                        row_filled += 1
                non_empty += row_filled
                if row_filled >= max(min(table_width * 0.3, 2), 1):
                    rows_with_data += 1
            fill_rate = non_empty / total_cells if total_cells > 0 else 0.0
            row_fill_rate = rows_with_data / table_rows if table_rows > 0 else 0.0
            # フォーム統合では行充填率を重視（元が多数の断片なので構造は確認済み）
            confidence = round(min(fill_rate * 0.2 + row_fill_rate * 0.85, 1.0), 3)

            merged_table = TableRegion(
                range=CellRange(
                    start_row=start_row,
                    start_col=all_start_col,
                    end_row=end_row,
                    end_col=all_end_col,
                ),
                layout=layout,
                confidence=confidence,
            )
            new_tables.append(merged_table)
            merged_indices.update(merge_targets)

        # 統合されなかったテーブルはそのまま保持
        result = [t for i, t in enumerate(tables) if i not in merged_indices]
        result.extend(new_tables)
        return result

    def _inherit_headers_from_above(self, sheet: Sheet, tables: list[TableRegion]) -> list[TableRegion]:
        """ヘッダーなしテーブルに直上テーブルのヘッダーを継承する。

        同一列範囲で垂直方向に近接するテーブルのうち、
        下側テーブルにヘッダーがなく上側にヘッダーがある場合、
        上側のヘッダー情報をコピーする。
        """
        if len(tables) <= 1:
            return tables

        # start_row 昇順でソート
        sorted_tables = sorted(tables, key=lambda t: t.range.start_row)

        # ヘッダー付きテーブルをインデックスする（列範囲 → テーブルリスト）
        for i, table in enumerate(sorted_tables):
            if table.layout.header_rows or table.layout.column_headers:
                continue

            # ヘッダーなしテーブル → 直上のテーブルを探す
            for j in range(i - 1, -1, -1):
                above = sorted_tables[j]

                # 列範囲一致チェック
                if above.range.start_col != table.range.start_col or above.range.end_col != table.range.end_col:
                    continue

                # 行ギャップチェック（空行2行まで許容）
                row_gap = table.range.start_row - above.range.end_row - 1
                if row_gap < 0 or row_gap > max(self.gap_threshold, 2):
                    continue

                # 上テーブルにヘッダーがあるか
                if not above.layout.column_headers:
                    continue

                # ヘッダーを継承
                inherited_headers = [
                    ColumnHeader(
                        col_index=ch.col_index,
                        header_rows=ch.header_rows,
                        label=ch.label,
                        is_merged=ch.is_merged,
                    )
                    for ch in above.layout.column_headers
                ]

                # 列スキーマも継承（下テーブルに columns がない場合）
                inherited_columns = table.layout.columns
                if not inherited_columns and above.layout.columns:
                    inherited_columns = _infer_column_schemas(
                        sheet,
                        table.layout.body_start_row,
                        table.layout.body_end_row,
                        table.range.start_col,
                        table.range.end_col,
                        inherited_headers,
                    )

                sorted_tables[i] = TableRegion(
                    range=table.range,
                    layout=TableLayout(
                        header_rows=[],
                        body_start_row=table.layout.body_start_row,
                        body_end_row=table.layout.body_end_row,
                        column_headers=inherited_headers,
                        columns=inherited_columns,
                        stub_cols=table.layout.stub_cols,
                        footer_rows=table.layout.footer_rows,
                    ),
                    confidence=table.confidence,
                    abstain=table.abstain,
                )
                logger.debug(
                    "ヘッダー継承: T(%s) → T(%s)",
                    above.range,
                    table.range,
                )
                break  # 最初にマッチした上テーブルから継承

        return sorted_tables


def _split_into_bands(indices: list[int], gap_threshold: int) -> list[tuple[int, int]]:
    """連続するインデックスをギャップで分割してバンドにする。

    Args:
        indices (list[int]): ソート済みインデックスリスト
        gap_threshold (int): この数以上の隙間があればバンドを分割

    Returns:
        list[tuple[int, int]]: (start, end) のリスト
    """
    if not indices:
        return []

    bands: list[tuple[int, int]] = []
    band_start = indices[0]
    prev = indices[0]

    for idx in indices[1:]:
        if idx - prev > gap_threshold:
            bands.append((band_start, prev))
            band_start = idx
        prev = idx

    bands.append((band_start, prev))
    return bands


def _merge_header_body_bands(
    sheet: Sheet,
    row_bands: list[tuple[int, int]],
    col_bands: list[tuple[int, int]],
    gap_tolerance: int,
) -> list[tuple[int, int]]:
    """ヘッダーのみのバンドと直後のデータバンドを統合する。

    行政Excelでは「ヘッダー行→空行→データ行」パターンが頻出するため、
    上バンドがヘッダー特徴のみで、下バンドが近接している場合に統合する。
    """
    if len(row_bands) <= 1:
        return row_bands

    # 各列バンドのうち最大の列幅を基準にヘッダー判定
    max_col_band = max(col_bands, key=lambda cb: cb[1] - cb[0] + 1) if col_bands else None
    if max_col_band is None:
        return row_bands

    start_col, end_col = max_col_band
    merged: list[tuple[int, int]] = []
    skip: set[int] = set()

    for i, band in enumerate(row_bands):
        if i in skip:
            continue

        current = band

        # 連続する次のバンドとのチェーン統合を試みる
        j = i + 1
        while j < len(row_bands) and j not in skip:
            next_band = row_bands[j]
            gap = next_band[0] - current[1] - 1

            if gap > gap_tolerance:
                break

            # 上バンドがヘッダー特徴を持つか判定
            band_rows = current[1] - current[0] + 1
            max_band_rows = _MAX_HEADER_ROWS + 5  # タイトル行分の余裕
            for mr in sheet.merged_cells:
                if (
                    mr.start_row >= current[0]
                    and mr.start_row <= current[1]
                    and mr.start_col >= start_col
                    and mr.end_col <= end_col
                ):
                    span = mr.end_row - mr.start_row + 1
                    if span >= 2:
                        max_band_rows = max(max_band_rows, band_rows + 2)
            is_header_band = band_rows <= max_band_rows and _band_is_header_like(
                sheet, current[0], current[1], start_col, end_col
            )

            if is_header_band:
                # 統合してチェーン継続
                logger.debug(
                    "ヘッダー・ボディ統合: (%d-%d) + (%d-%d) → (%d-%d)",
                    current[0],
                    current[1],
                    next_band[0],
                    next_band[1],
                    current[0],
                    next_band[1],
                )
                current = (current[0], next_band[1])
                skip.add(j)
                j += 1
            else:
                break

        merged.append(current)

    return merged


def _band_is_header_like(sheet: Sheet, start_row: int, end_row: int, start_col: int, end_col: int) -> bool:
    """バンド内にヘッダー特徴を持つ行があり、数値データ行がないか判定する。

    タイトル行・空行が含まれていても、強いヘッダーシグナル（太字/結合）が
    存在し、かつ数値データ行がなければヘッダーバンドとみなす。
    """
    table_width = end_col - start_col + 1
    has_strong_header = False
    has_data_row = False

    for row in range(start_row, end_row + 1):
        strength = _header_row_strength(sheet, row, start_col, end_col)
        if strength >= 2:
            has_strong_header = True
            continue
        if strength == 1:
            continue

        # strength == 0 の行を確認
        row_values = []
        for c in range(start_col, end_col + 1):
            cell = sheet.get_cell(row, c)
            if cell and cell.value is not None:
                row_values.append(cell.value)

        if not row_values:
            continue  # 空行は許容

        # 非空セルが少ない（タイトル行等）は許容
        if len(row_values) <= 2 and table_width >= 3:
            continue

        # 数値を含む高充填率行 → データ行
        has_numeric = any(isinstance(v, (int, float)) for v in row_values)
        # CSV対応: 数値パターン文字列もデータとみなす
        if not has_numeric:
            has_numeric = any(
                isinstance(v, str) and _is_numeric_string(v.strip()) and _is_data_like_number(v.strip())
                for v in row_values
                if isinstance(v, str) and v.strip()
            )
        fill_rate = len(row_values) / table_width
        if has_numeric and fill_rate > 0.3:
            has_data_row = True

    return has_strong_header and not has_data_row


def _header_row_strength(sheet: Sheet, row: int, start_col: int, end_col: int) -> int:
    """行がヘッダー行の特徴を持つか判定し、強度を返す。

    Returns:
        int: 0: ヘッダーではない
            1: 弱いシグナル（全文字列のみ）
            2: 強いシグナル（太字または結合セル）
    """
    row_cells = [sheet.get_cell(row, c) for c in range(start_col, end_col + 1)]
    non_empty = [c for c in row_cells if c is not None and c.value is not None]

    if not non_empty:
        return 0

    strength = 0

    # 太字チェック → 強シグナル
    if any(c.fmt.bold for c in non_empty):
        return 2

    # 結合セルチェック → 強シグナル
    if any(c.is_merged for c in non_empty):
        vertical_merge_count = 0
        for mr in sheet.merged_cells:
            if mr.start_row <= row and mr.end_row >= row:
                if mr.start_col >= start_col and mr.end_col <= end_col:
                    # 水平方向に2列以上スパン → 強シグナル
                    if mr.end_col > mr.start_col:
                        return 2
                    # 垂直方向のみの結合をカウント
                    if mr.end_row > mr.start_row:
                        vertical_merge_count += 1
        # 垂直結合が多数（3つ以上）あれば、ヘッダー行の書式設定と判断
        if vertical_merge_count >= 3:
            return 2

    # 全て文字列チェック → 弱シグナル
    # ただし、データらしい数値文字列（3桁以上、カンマ付き、小数点付き）が
    # 多数含まれる場合はヘッダーとしない（列番号のような1-2桁整数は許容）
    # 欠損値プレースホルダーは無視する
    if all(isinstance(c.value, str) for c in non_empty):
        data_like_count = 0
        meaningful_count = 0
        for c in non_empty:
            if isinstance(c.value, str) and c.value.strip():
                s = c.value.strip()
                if s in _MISSING_PLACEHOLDERS:
                    continue
                meaningful_count += 1
                if _is_numeric_string(s) and _is_data_like_number(s):
                    data_like_count += 1
        denominator = max(meaningful_count, 1)
        if data_like_count <= denominator * 0.3:
            strength = 1

    return strength


def _row_type_signature(sheet: Sheet, row: int, start_col: int, end_col: int) -> tuple[str, ...]:
    """行の各セルの型タグのタプルを返す。"""
    sig: list[str] = []
    for c in range(start_col, end_col + 1):
        cell = sheet.get_cell(row, c)
        if cell is None or cell.value is None:
            sig.append("none")
        elif isinstance(cell.value, (int, float)):
            sig.append("num")
        elif isinstance(cell.value, str):
            sig.append("str")
        else:
            sig.append("other")
    return tuple(sig)


def _is_header_row(sheet: Sheet, row: int, start_col: int, end_col: int) -> bool:
    """行がヘッダー行の特徴を持つか判定する。"""
    return _header_row_strength(sheet, row, start_col, end_col) > 0


def _has_merged_cells_in_range(sheet: Sheet, start_row: int, end_row: int, start_col: int, end_col: int) -> bool:
    """指定範囲内に結合セルがあるか確認する。"""
    for mr in sheet.merged_cells:
        # 結合範囲が指定領域と重なるか判定
        if mr.start_row <= end_row and mr.end_row >= start_row and mr.start_col <= end_col and mr.end_col >= start_col:
            return True
    return False


def _trim_boundaries(
    sheet: Sheet,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
) -> tuple[int, int, list[OtherCell]]:
    """テーブル境界のトリミング: タイトル行・合計行・備考行・出典行を分離する。

    Args:
        sheet (Sheet): 対象シート
        start_row (int): 行範囲の開始行
        end_row (int): 行範囲の終了行
        start_col (int): 列範囲の開始列
        end_col (int): 列範囲の終了列

    Returns:
        tuple[int, int, list[OtherCell]]: (トリミング後の start_row, end_row, 分離された OtherCell のリスト)
    """
    others: list[OtherCell] = []
    table_width = end_col - start_col + 1
    trimmed_start = start_row
    trimmed_end = end_row

    # ── 先頭行のトリミング: タイトル行・メタデータ行 ──
    # テーブル幅が3列以上で、先頭行の非空セルが1-2個のみ → タイトル/メタデータ行
    # ただし、結合セルや太字を含む行はヘッダー行の可能性が高いのでスキップ
    # 連続する低充填率行を全て分離する（ループ）
    while table_width >= 3 and trimmed_start < trimmed_end:
        first_row_non_empty = 0
        has_header_signal = False
        for c in range(start_col, end_col + 1):
            cell = sheet.get_cell(trimmed_start, c)
            if cell and cell.value is not None:
                first_row_non_empty += 1
            if cell and (cell.is_merged or cell.fmt.bold):
                has_header_signal = True

        # タイトル行の判定:
        # 1. 非空セル1個 + 太字/結合 + テーブル幅4列以上 → タイトル
        # 2. 充填率15%以下でヘッダーシグナルなし → メタデータ/タイトル行
        # 3. 非空セル1-2個でヘッダーシグナルなし → タイトル行（従来ロジック）
        fill_rate = first_row_non_empty / table_width if table_width > 0 else 1.0
        is_title = False
        if first_row_non_empty == 1 and has_header_signal and table_width >= 4:
            # 太字/結合の1セル行 + テーブル幅4列以上 → タイトル
            # （幅3列以下では結合ヘッダーの可能性が高いので除外）
            is_title = True
        elif fill_rate <= 0.15 and not has_header_signal:
            # 充填率15%以下（CSV等で3セル以上でも低充填率ならタイトル）
            is_title = True
        elif 1 <= first_row_non_empty <= 2 and not has_header_signal:
            is_title = True

        if is_title:
            for c in range(start_col, end_col + 1):
                cell = sheet.get_cell(trimmed_start, c)
                if cell and cell.value is not None:
                    others.append(
                        OtherCell(
                            row=trimmed_start,
                            col=c,
                            value=cell.value,
                            region_type="title",
                        )
                    )
            trimmed_start += 1
        else:
            break

    # ── 末尾行のトリミング（末尾から逆順にチェック） ──
    while trimmed_end > trimmed_start:
        row = trimmed_end
        row_cells = []
        for c in range(start_col, end_col + 1):
            cell = sheet.get_cell(row, c)
            row_cells.append(cell)

        non_empty_cells = [c for c in row_cells if c is not None and c.value is not None]

        if not non_empty_cells:
            trimmed_end -= 1
            continue

        # 合計行: =SUM / =SUBTOTAL 数式を含む行
        has_sum_formula = any(
            c.formula and re.match(r"^=\s*(SUM|SUBTOTAL)\b", c.formula, re.IGNORECASE)
            for c in non_empty_cells
            if c.formula
        )
        if has_sum_formula:
            for c_obj in non_empty_cells:
                others.append(
                    OtherCell(
                        row=row,
                        col=c_obj.pos.col,
                        value=c_obj.value,
                        region_type="total",
                    )
                )
            trimmed_end -= 1
            continue

        # 合計行: 日本語キーワードによる検出（ハードコード値の合計行）
        has_total_keyword = _is_total_row(non_empty_cells)
        if has_total_keyword:
            for c_obj in non_empty_cells:
                others.append(
                    OtherCell(
                        row=row,
                        col=c_obj.pos.col,
                        value=c_obj.value,
                        region_type="total",
                    )
                )
            trimmed_end -= 1
            continue

        # 備考行: 先頭セルが「※」「（注）」「注：」「注）」「備考」で始まる
        first_value = non_empty_cells[0].value if non_empty_cells else None
        if isinstance(first_value, str) and re.match(r"^\s*(※|（注）|注[：:）)]|備考)", first_value):
            for c_obj in non_empty_cells:
                others.append(
                    OtherCell(
                        row=row,
                        col=c_obj.pos.col,
                        value=c_obj.value,
                        region_type="note",
                    )
                )
            trimmed_end -= 1
            continue

        # 出典行: 充填率30%未満
        fill_rate = len(non_empty_cells) / table_width
        if fill_rate < 0.3 and isinstance(first_value, str):
            # 「出典」「source」で始まるか、充填率が低い文字列行
            is_source = first_value.strip().startswith(("出典", "Source", "source", "参考", "出所", "資料"))
            if is_source or fill_rate <= 0.2:
                for c_obj in non_empty_cells:
                    others.append(
                        OtherCell(
                            row=row,
                            col=c_obj.pos.col,
                            value=c_obj.value,
                            region_type="source" if is_source else "note",
                        )
                    )
                trimmed_end -= 1
                continue

        # マッチしなかったら末尾トリミング終了
        break

    # ── 残り1行のメタデータチェック ──
    # トリミング後に1行だけ残り、低充填率・文字列のみの場合はメタデータとして分離
    if trimmed_start == trimmed_end and table_width >= 3:
        row = trimmed_start
        non_empty_cells = []
        for c in range(start_col, end_col + 1):
            cell = sheet.get_cell(row, c)
            if cell and cell.value is not None:
                non_empty_cells.append(cell)
        fill_rate = len(non_empty_cells) / table_width
        if fill_rate <= 0.2 and non_empty_cells and all(isinstance(c.value, str) for c in non_empty_cells):
            for c_obj in non_empty_cells:
                others.append(
                    OtherCell(
                        row=row,
                        col=c_obj.pos.col,
                        value=c_obj.value,
                        region_type="note",
                    )
                )
            trimmed_start = trimmed_end + 1  # 有効行なし

    return trimmed_start, trimmed_end, others


def _estimate_layout(
    sheet: Sheet,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
    max_header_rows: int = _MAX_HEADER_ROWS,
) -> TableLayout:
    """レイアウト推定: ヘッダー行を特定する。

    マルチ行ヘッダー対応のヒューリスティック:
    1. 先頭から最大 max_header_rows 行まで連続してヘッダー特徴を持つ行を検出
    2. ヘッダー特徴: 太字、全文字列、結合セルのいずれか
    3. ヘッダー候補行の次の行にデータ行（数値を含む）があれば確定
    4. ヘッダー領域内の結合セルも考慮
    """
    if start_row == end_row:
        # 1行しかない場合はヘッダーなし
        return TableLayout(
            header_rows=[],
            body_start_row=start_row,
            body_end_row=end_row,
        )

    # 結合セルのスパンに基づいて max_header_rows を動的に拡張
    effective_max_header = max_header_rows
    for mr in sheet.merged_cells:
        if (
            mr.start_row >= start_row
            and mr.start_row < start_row + max_header_rows
            and mr.end_row > start_row + max_header_rows - 1
            and mr.start_col >= start_col
            and mr.end_col <= end_col
        ):
            effective_max_header = max(effective_max_header, mr.end_row - start_row + 1)
    # 上限: テーブル行数の半分まで
    effective_max_header = min(effective_max_header, max((end_row - start_row + 1) // 2, max_header_rows))

    # 先頭から連続するヘッダー候補行を検出（強度付き）
    header_candidates: list[int] = []
    candidate_strengths: list[int] = []
    max_check = min(start_row + effective_max_header, end_row + 1)

    for row in range(start_row, max_check):
        strength = _header_row_strength(sheet, row, start_col, end_col)
        if strength > 0:
            header_candidates.append(row)
            candidate_strengths.append(strength)
        else:
            # 空行は1行まで許容して走査を継続（ヘッダー内空行への対応）
            row_is_empty = True
            for c in range(start_col, end_col + 1):
                cell = sheet.get_cell(row, c)
                if cell and cell.value is not None:
                    row_is_empty = False
                    break
            if row_is_empty and row + 1 < max_check:
                # 次の行にヘッダー特徴があれば空行をスキップして継続
                next_strength = _header_row_strength(sheet, row + 1, start_col, end_col)
                if next_strength > 0:
                    continue  # 空行をスキップ
            break

    if not header_candidates:
        # ヘッダー特徴なし: 先頭行の型パターンと後続行を比較して判断
        if start_row < end_row:
            first_sig = _row_type_signature(sheet, start_row, start_col, end_col)
            next_sig = _row_type_signature(sheet, start_row + 1, start_col, end_col)
            has_numeric = any(t == "num" for t in first_sig)
            if has_numeric and first_sig == next_sig:
                # 数値を含み後続行と同じ型パターン → ボディ行（ヘッダーなし）
                return TableLayout(
                    header_rows=[],
                    body_start_row=start_row,
                    body_end_row=end_row,
                )
        # それ以外は先頭行をヘッダーと仮定し、続く行もヘッダー候補か確認
        header_candidates = [start_row]
        candidate_strengths = [0]
        for row in range(start_row + 1, max_check):
            strength = _header_row_strength(sheet, row, start_col, end_col)
            if strength > 0:
                header_candidates.append(row)
                candidate_strengths.append(strength)
            else:
                break

    # 複数行結合によるヘッダー深さの制限:
    # ヘッダー候補行から始まる複数行結合のスパンでヘッダー深さを決定し、
    # スパン外の行をトリミング（データ行の横結合による誤包含を防ぐ）
    has_strong = any(s >= 2 for s in candidate_strengths)
    if has_strong and len(header_candidates) > 1:
        candidate_set = set(header_candidates)
        merge_defined_end = header_candidates[0]
        has_defining_merges = False
        for mr in sheet.merged_cells:
            if (
                mr.start_col >= start_col
                and mr.end_col <= end_col
                and mr.end_row > mr.start_row  # 複数行にスパンする結合のみ
                and mr.start_row in candidate_set
            ):
                has_defining_merges = True
                merge_defined_end = max(merge_defined_end, mr.end_row)
        if has_defining_merges:
            trimmed_h = []
            trimmed_s = []
            for r, s in zip(header_candidates, candidate_strengths):
                if r <= merge_defined_end:
                    trimmed_h.append(r)
                    trimmed_s.append(s)
            header_candidates = trimmed_h
            candidate_strengths = trimmed_s

    # 弱シグナルのみの候補が複数ある場合、後続行がデータかどうかで判断
    # 全候補が弱シグナル(=1: 全文字列)の場合、候補の直後に数値データ行がなければ
    # ヘッダーは先頭1行のみとする（全文字列テーブルの誤検出を防ぐ）
    if not has_strong and len(header_candidates) > 1:
        # 最後の候補の次にデータ行（数値含む）があるか確認
        tentative_body = header_candidates[-1] + 1
        has_numeric_after = False
        if tentative_body <= end_row:
            for c in range(start_col, end_col + 1):
                cell = sheet.get_cell(tentative_body, c)
                if cell is None or cell.value is None:
                    continue
                if isinstance(cell.value, (int, float)):
                    has_numeric_after = True
                    break
                # CSV対応: 数値パターンの文字列もデータとみなす
                if (
                    isinstance(cell.value, str)
                    and _is_numeric_string(cell.value.strip())
                    and _is_data_like_number(cell.value.strip())
                ):
                    has_numeric_after = True
                    break

        if not has_numeric_after:
            # データ行がない → 先頭行のみヘッダーに限定
            header_candidates = [header_candidates[0]]
            candidate_strengths = [candidate_strengths[0]]
        elif tentative_body <= end_row:
            # データ行があっても、候補行と型パターンが同一なら
            # ヘッダーとデータの区別がつかない → 先頭行のみに限定
            first_sig = _row_type_signature(sheet, header_candidates[0], start_col, end_col)
            body_sig = _row_type_signature(sheet, tentative_body, start_col, end_col)
            if first_sig == body_sig:
                header_candidates = [header_candidates[0]]
                candidate_strengths = [candidate_strengths[0]]

    # 充填率チェック: ヘッダー候補行のうち、他の候補行に比べて非空セルが
    # 極端に少ない行はセクションラベル（例: "総数"）と判断して除外
    # 結合セルは実際のカバー列数でカウント
    if len(header_candidates) > 1:
        fills = []
        for r in header_candidates:
            covered = set()
            for c in range(start_col, end_col + 1):
                cell = sheet.get_cell(r, c)
                if cell and cell.value is not None:
                    covered.add(c)
            # 結合セルのスパンをカバー列数に含める
            for mr in sheet.merged_cells:
                if mr.start_row <= r <= mr.end_row:
                    for c in range(max(mr.start_col, start_col), min(mr.end_col, end_col) + 1):
                        covered.add(c)
            fills.append(len(covered))
        max_fill = max(fills)
        col_count = end_col - start_col + 1
        if max_fill > 0:
            trimmed_h = []
            trimmed_s = []
            for r, s, f in zip(header_candidates, candidate_strengths, fills):
                # 最大充填率の20%未満かつテーブル幅の30%未満の行は除外
                if f >= max_fill * 0.2 or f >= col_count * 0.3:
                    trimmed_h.append(r)
                    trimmed_s.append(s)
            if trimmed_h:
                header_candidates = trimmed_h
                candidate_strengths = trimmed_s

    # ヘッダー候補が複数ある場合、結合セルによるスパンを確認して拡張
    if len(header_candidates) >= 1:
        last_header = header_candidates[-1]
        # ヘッダー領域内に結合セルがあり、その結合が候補行を超えて
        # 次の行まで伸びている場合、その行もヘッダーに含める
        for mr in sheet.merged_cells:
            if (
                mr.start_row >= start_row
                and mr.start_row <= last_header
                and mr.end_row > last_header
                and mr.end_row <= min(start_row + max_header_rows - 1, end_row - 1)
                and mr.start_col >= start_col
                and mr.end_col <= end_col
            ):
                for extra_row in range(last_header + 1, mr.end_row + 1):
                    if extra_row not in header_candidates:
                        header_candidates.append(extra_row)
                        last_header = max(last_header, extra_row)

    # ヘッダー候補の次の行がデータ行かどうかを確認してログ出力
    body_start = header_candidates[-1] + 1
    if body_start <= end_row:
        next_row_has_data = False
        for c in range(start_col, end_col + 1):
            cell = sheet.get_cell(body_start, c)
            if cell and isinstance(cell.value, (int, float)):
                next_row_has_data = True
                break
        if not next_row_has_data:
            logger.debug("ヘッダー候補行 %s の後にデータ行が見つかりません", header_candidates)

    sorted_headers = sorted(header_candidates)
    body_start_final = body_start if body_start <= end_row else end_row

    # ヘッダー行数の安全制限:
    # 1. ヘッダーが5行以上かつボディが2行以下 → 先頭1行に縮小
    # 2. ヘッダーが max_header_rows 超過 → 制限内に縮小
    body_rows_count = end_row - body_start_final + 1 if body_start_final <= end_row else 0
    if len(sorted_headers) >= 5 and body_rows_count <= 2:
        sorted_headers = sorted_headers[:1]
        body_start_final = sorted_headers[0] + 1
    elif len(sorted_headers) > max_header_rows:
        sorted_headers = sorted_headers[:max_header_rows]
        body_start_final = sorted_headers[-1] + 1

    # ColumnHeader 生成
    column_headers = _generate_column_headers(sheet, sorted_headers, start_col, end_col)

    # 列型推定
    columns = _infer_column_schemas(sheet, body_start_final, end_row, start_col, end_col, column_headers)

    # 行ヘッダー推定
    stub_cols = _estimate_stub_cols(sheet, body_start_final, end_row, start_col, end_col, columns)

    return TableLayout(
        header_rows=sorted_headers,
        body_start_row=body_start_final,
        body_end_row=end_row,
        column_headers=column_headers,
        columns=columns,
        stub_cols=stub_cols,
    )


# 日付パターン（保守的）
_DATE_PATTERNS = [
    re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"),
    re.compile(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$"),
]


def _generate_column_headers(
    sheet: Sheet,
    header_rows: list[int],
    start_col: int,
    end_col: int,
) -> list[ColumnHeader]:
    """ヘッダー行から列ごとの ColumnHeader を生成する。

    Args:
        sheet (Sheet): 対象シート
        header_rows (list[int]): ヘッダー行のリスト（ソート済み）
        start_col (int): 列範囲の開始列
        end_col (int): 列範囲の終了列

    Returns:
        list[ColumnHeader]
    """
    if not header_rows:
        return []

    result: list[ColumnHeader] = []
    for col in range(start_col, end_col + 1):
        labels: list[str] = []
        is_merged = False
        for row in header_rows:
            cell = sheet.get_cell(row, col)
            if cell is not None:
                if cell.is_merged:
                    is_merged = True
                value = cell.value
                # 結合セルのスレーブ（値がない）場合、マスターセルの値を取得
                if value is None and cell.merge_master is not None:
                    master = sheet.get_cell(cell.merge_master.row, cell.merge_master.col)
                    if master is not None:
                        value = master.value
                if value is not None:
                    label_str = str(value).strip()
                    # 同じラベルの重複を避ける（結合セルで同値が連続する場合）
                    if label_str and (not labels or labels[-1] != label_str):
                        labels.append(label_str)

        result.append(
            ColumnHeader(
                col_index=col,
                header_rows=list(header_rows),
                label=" / ".join(labels) if labels else "",
                is_merged=is_merged,
            )
        )

    return result


def _infer_column_schemas(
    sheet: Sheet,
    body_start_row: int,
    body_end_row: int,
    start_col: int,
    end_col: int,
    column_headers: list[ColumnHeader],
) -> list[ColumnSchema]:
    """ボディ部の各列の値型を推定する。

    Args:
        sheet (Sheet): 対象シート
        body_start_row (int): ボディ行範囲の開始行
        body_end_row (int): ボディ行範囲の終了行
        start_col (int): 列範囲の開始列
        end_col (int): 列範囲の終了列
        column_headers (list[ColumnHeader]): 対応する列ヘッダー

    Returns:
        list[ColumnSchema]
    """
    # ColumnHeader の col_index → label マップ
    header_map: dict[int, str] = {}
    for ch in column_headers:
        header_map[ch.col_index] = ch.label

    result: list[ColumnSchema] = []
    for col in range(start_col, end_col + 1):
        type_counts: dict[str, int] = {
            "numeric": 0,
            "text": 0,
            "date": 0,
            "empty": 0,
        }

        for row in range(body_start_row, body_end_row + 1):
            cell = sheet.get_cell(row, col)
            if cell is None or cell.value is None:
                type_counts["empty"] += 1
                continue

            value = cell.value
            if isinstance(value, (int, float)):
                type_counts["numeric"] += 1
            elif isinstance(value, (datetime, date, time)):
                type_counts["date"] += 1
            elif isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    type_counts["empty"] += 1
                elif stripped in _MISSING_PLACEHOLDERS:
                    type_counts["empty"] += 1
                elif _is_date_string(stripped):
                    type_counts["date"] += 1
                elif _is_numeric_string(stripped):
                    type_counts["numeric"] += 1
                else:
                    type_counts["text"] += 1
            else:
                type_counts["text"] += 1

        inferred_type = _determine_column_type(type_counts)
        has_header = bool(header_map.get(col, ""))

        result.append(
            ColumnSchema(
                col_index=col,
                inferred_type=inferred_type,
                has_header=has_header,
            )
        )

    return result


def _is_date_string(s: str) -> bool:
    """文字列が日付パターンにマッチするか判定する。"""
    return any(p.match(s) for p in _DATE_PATTERNS)


def _is_numeric_string(s: str) -> bool:
    """文字列が数値パターンにマッチするか判定する（CSV対応）。"""
    return any(p.match(s) for p in _NUMERIC_STR_PATTERNS)


def _is_data_like_number(s: str) -> bool:
    """数値文字列がデータ値らしいか判定する。

    列番号のような1-2桁の小さい整数はFalse（ヘッダーメタデータとして許容）。
    3桁以上の整数、カンマ区切り、小数点付きはTrue（データ値らしい）。
    """
    # カンマ区切りや小数点を含む → データ値
    if "," in s or "." in s:
        return True
    # 符号を除去して桁数チェック
    digits = s.lstrip("+-")
    return len(digits) >= 3


def _is_total_row(cells: list) -> bool:
    """セルリスト内に合計キーワードを含む行か判定する。

    先頭から3セル以内の文字列セルが合計キーワードに完全一致する場合に True。
    """
    checked = 0
    for cell in cells:
        if cell is not None and isinstance(cell.value, str):
            stripped = cell.value.strip()
            if _TOTAL_KEYWORDS.match(stripped):
                return True
            checked += 1
            if checked >= 3:
                break
    return False


def _determine_column_type(
    type_counts: dict[str, int],
) -> Literal["text", "numeric", "date", "mixed", "empty"]:
    """型カウントから列型を決定する。"""
    total = sum(type_counts.values())
    non_empty = total - type_counts["empty"]

    if non_empty == 0:
        return "empty"

    # 80%以上が同一型なら確定
    threshold = non_empty * 0.8
    if type_counts["numeric"] >= threshold:
        return "numeric"
    if type_counts["date"] >= threshold:
        return "date"
    if type_counts["text"] >= threshold:
        return "text"

    return "mixed"


def _is_code_like_integers(values: list) -> bool:
    """整数の連番・IDリストかどうかを判定する（stub 判定専用）。

    以下をすべて満たす場合に True を返す:
    - 全値が整数、小数部ゼロの float、またはゼロパディング文字列（"001" 等）
    - 全値が正の整数
    - 全値が一意（重複なし）
    """
    if len(values) < 2:
        return False
    seen: set[int] = set()
    for v in values:
        if isinstance(v, int):
            i = v
        elif isinstance(v, float) and v.is_integer():
            i = int(v)
        elif isinstance(v, str) and v.strip().isdigit():
            i = int(v.strip())
        else:
            return False
        if i <= 0 or i in seen:
            return False
        seen.add(i)
    return True


def _stub_col_score(
    sheet: Sheet,
    body_start_row: int,
    body_end_row: int,
    col: int,
    end_col: int,
    schema_map: dict[int, ColumnSchema],
) -> int:
    """1列分の行ヘッダースコアを計算する。"""
    schema = schema_map.get(col)

    if body_start_row > body_end_row:
        if not schema:
            return 0
        if schema.inferred_type == "text":
            return 2
        if schema.inferred_type == "mixed":
            return 1
        if schema.inferred_type in ("numeric", "date"):
            return -2
        return 0

    rows = range(body_start_row, body_end_row + 1)

    # 1パスで全ボディセルと非空セルを収集
    all_cells = [c for r in rows if (c := sheet.get_cell(r, col)) is not None]
    non_empty = [c for c in all_cells if c.value is not None]

    type_score = 0
    if schema:
        if schema.inferred_type == "text":
            type_score = 2
        elif schema.inferred_type == "mixed":
            type_score = 1
        elif schema.inferred_type == "numeric":
            numeric_values = [c.value for c in non_empty]
            type_score = 0 if _is_code_like_integers(numeric_values) else -2
        elif schema.inferred_type == "date":
            type_score = -2

    n_rows = len(rows)

    def _right_boundary_rate(c: int) -> float:
        """列 c の右境界の罫線出現率（c の border_right または c+1 の border_left）。"""
        if n_rows == 0:
            return 0.0
        count = 0
        for r in rows:
            cell = sheet.get_cell(r, c)
            adj = sheet.get_cell(r, c + 1) if c < end_col else None
            if (cell is not None and cell.fmt.border_right is not None) or (
                adj is not None and adj.fmt.border_left is not None
            ):
                count += 1
        return count / n_rows

    if col < end_col:
        border_right_score = (
            2 if _right_boundary_rate(col) - _right_boundary_rate(col + 1) > _STUB_FMT_RATE_THRESHOLD else 0
        )
    else:
        border_right_score = 0

    if not non_empty:
        return type_score + border_right_score

    total_ne = len(non_empty)
    bg_score = (
        2
        if sum(1 for c in non_empty if c.fmt.bg_color is not None and c.fmt.bg_color not in _NO_BG_COLORS) / total_ne
        > _STUB_FMT_RATE_THRESHOLD
        else 0
    )
    bold_score = 1 if sum(1 for c in non_empty if c.fmt.bold) / total_ne > _STUB_FMT_RATE_THRESHOLD else 0
    return type_score + border_right_score + bg_score + bold_score


def _estimate_stub_cols(
    sheet: Sheet,
    body_start_row: int,
    body_end_row: int,
    start_col: int,
    end_col: int,
    columns: list[ColumnSchema],
) -> list[int]:
    """行ヘッダー列（stub_cols）を左端から推定する。"""
    total_cols = end_col - start_col + 1
    max_stubs = min(_MAX_STUB_COLS, total_cols - 1)
    if max_stubs <= 0:
        return []

    schema_map = {s.col_index: s for s in columns}
    stub_cols: list[int] = []

    for col in range(start_col, start_col + max_stubs):
        score = _stub_col_score(sheet, body_start_row, body_end_row, col, end_col, schema_map)
        if score >= _STUB_SCORE_THRESHOLD:
            stub_cols.append(col)

    return stub_cols
