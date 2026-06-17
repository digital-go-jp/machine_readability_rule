"""ルールテスト共通fixture"""

from __future__ import annotations

from typing import Any

import pytest

from harunobu.core.layout.island import _infer_column_schemas
from harunobu.core.models import (
    Cell,
    CellPosition,
    CellRange,
    ColumnSchema,
    Config,
    MergedRange,
    Sheet,
    TableContext,
    TableLayout,
    TableRegion,
    WorkBook,
)


@pytest.fixture
def create_workbook():
    """テスト用WorkBookをプログラム的に生成するfixture。

    Args:
        sheets_data
            {"Sheet1": [["A", "B"], [1, 2]]} 形式のシートデータ
        file_name
            ファイル名 (default: "test.xlsx")
        merged_cells
            [{"sheet": "Sheet1", "start_row": 1, "start_col": 1,
            "end_row": 1, "end_col": 3}] 形式の結合セル情報
        hidden_rows
            {"Sheet1": [2, 3]} 形式の非表示行
        hidden_cols
            {"Sheet1": [1]} 形式の非表示列
        formulas
            {"Sheet1": {(1, 1): "=SUM(A2:A10)"}} 形式の数式
    """

    def _create(
        sheets_data: dict[str, list[list[Any]]],
        file_name: str = "test.xlsx",
        merged_cells: list[dict[str, Any]] | None = None,
        hidden_rows: dict[str, list[int]] | None = None,
        hidden_cols: dict[str, list[int]] | None = None,
        formulas: dict[str, dict[tuple[int, int], str]] | None = None,
        encoding: str | None = None,
    ) -> WorkBook:
        sheets: list[Sheet] = []
        file_format = "xlsx"
        if file_name.endswith(".csv"):
            file_format = "csv"
        elif file_name.endswith(".tsv"):
            file_format = "tsv"

        for sheet_name, rows in sheets_data.items():
            cells: dict[tuple[int, int], Cell] = {}
            max_row = len(rows)
            max_col = 0

            for r_idx, row in enumerate(rows, start=1):
                if len(row) > max_col:
                    max_col = len(row)
                for c_idx, value in enumerate(row, start=1):
                    pos = CellPosition(row=r_idx, col=c_idx)
                    formula = None
                    if formulas and sheet_name in formulas:
                        formula = formulas[sheet_name].get((r_idx, c_idx))
                    cells[(r_idx, c_idx)] = Cell(
                        pos=pos,
                        value=value,
                        formula=formula,
                    )

            # 結合セル情報
            sheet_merged: list[MergedRange] = []
            if merged_cells:
                for mc in merged_cells:
                    if mc.get("sheet") == sheet_name:
                        sheet_merged.append(
                            MergedRange(
                                start_row=mc["start_row"],
                                start_col=mc["start_col"],
                                end_row=mc["end_row"],
                                end_col=mc["end_col"],
                            )
                        )
                        # 結合セルのis_mergedフラグを設定
                        for r in range(mc["start_row"], mc["end_row"] + 1):
                            for c in range(mc["start_col"], mc["end_col"] + 1):
                                if (r, c) in cells:
                                    cells[(r, c)].is_merged = True
                                    if r != mc["start_row"] or c != mc["start_col"]:
                                        cells[(r, c)].merge_master = CellPosition(
                                            row=mc["start_row"],
                                            col=mc["start_col"],
                                        )

            sheet_hidden_rows: list[int] = []
            if hidden_rows and sheet_name in hidden_rows:
                sheet_hidden_rows = hidden_rows[sheet_name]

            sheet_hidden_cols: list[int] = []
            if hidden_cols and sheet_name in hidden_cols:
                sheet_hidden_cols = hidden_cols[sheet_name]

            sheets.append(
                Sheet(
                    name=sheet_name,
                    cells=cells,
                    merged_cells=sheet_merged,
                    max_row=max_row,
                    max_col=max_col,
                    hidden_rows=sheet_hidden_rows,
                    hidden_cols=sheet_hidden_cols,
                )
            )

        return WorkBook(
            file_name=file_name,
            file_format=file_format,
            sheets=sheets,
            encoding=encoding,
        )

    return _create


@pytest.fixture
def create_context(create_workbook):
    """テスト用TableContextを生成するfixture。

    create_workbookと同じ引数を受け取り、最初のシートのTableContextを返す。
    sheet_indexを指定すると対象シートを変更可能。
    """

    def _create(
        sheets_data: dict[str, list[list[Any]]],
        *,
        sheet_index: int = 0,
        file_name: str = "test.xlsx",
        merged_cells: list[dict[str, Any]] | None = None,
        hidden_rows: dict[str, list[int]] | None = None,
        hidden_cols: dict[str, list[int]] | None = None,
        formulas: dict[str, dict[tuple[int, int], str]] | None = None,
        config: Config | None = None,
        column_schemas: list[ColumnSchema] | None = None,
        encoding: str | None = None,
        stub_cols: list[int] | None = None,
    ) -> TableContext:
        workbook = create_workbook(
            sheets_data=sheets_data,
            file_name=file_name,
            merged_cells=merged_cells,
            hidden_rows=hidden_rows,
            hidden_cols=hidden_cols,
            formulas=formulas,
            encoding=encoding,
        )
        sheet = workbook.sheets[sheet_index]

        body_start = 2
        body_end = sheet.max_row
        if column_schemas is not None:
            columns = column_schemas
        else:
            columns = (
                _infer_column_schemas(sheet, body_start, body_end, 1, sheet.max_col, [])
                if body_end >= body_start and sheet.max_col > 0
                else []
            )

        table_region = TableRegion(
            range=CellRange(
                start_row=1,
                start_col=1,
                end_row=sheet.max_row,
                end_col=sheet.max_col,
            ),
            layout=TableLayout(
                header_rows=[1],
                body_start_row=body_start,
                body_end_row=body_end,
                columns=columns,
                stub_cols=stub_cols or [],
            ),
            columns=columns,
            confidence=1.0,
        )

        return TableContext(
            workbook=workbook,
            sheet=sheet,
            table_region=table_region,
            config=config or Config(),
        )

    return _create
