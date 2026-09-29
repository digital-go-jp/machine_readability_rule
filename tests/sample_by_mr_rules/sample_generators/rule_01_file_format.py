"""L1-01 用サンプル。"""

from __future__ import annotations

from pathlib import Path

from .common import base_rows, make_empty_workbook, save_workbook, write_docx_table, write_pdf_table, write_rows


def generate(output_dir: Path) -> list[Path]:
    rows = base_rows(english=True)

    workbook, sheet = make_empty_workbook(first_sheet_title="Population Data")
    write_rows(sheet, rows)

    xlsx_path = save_workbook(output_dir, workbook, "rule_01_file_format_OK")
    pdf_path = write_pdf_table(output_dir, "rule_01_file_format_NG-01.pdf", rows)
    docx_path = write_docx_table(output_dir, "rule_01_file_format_NG-02.docx", rows)

    return [xlsx_path, pdf_path, docx_path]
