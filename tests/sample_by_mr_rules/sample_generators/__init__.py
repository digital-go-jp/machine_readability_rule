"""機械可読性ルール別サンプル生成器（登録番号は RULE_GENERATORS_BY_NUMBER を参照）。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .rule_01_file_format import generate as generate_rule_01_file_format
from .rule_02_multiple_tables import generate as generate_rule_02_multiple_tables
from .rule_03_fragmented_data import generate as generate_rule_03_fragmented_data
from .rule_04_extraneous_info import generate as generate_rule_04_extraneous_info
from .rule_05_missing_column_names import generate as generate_rule_05_missing_column_names
from .rule_06_space_formatting import generate as generate_rule_06_space_formatting
from .rule_07_one_cell_one_data import generate as generate_rule_07_one_cell_one_data
from .rule_08_platform_dependent_chars import generate as generate_rule_08_platform_dependent_chars
from .rule_10_excel_objects import generate as generate_rule_10_excel_objects
from .rule_11_format_based_semantics import generate as generate_rule_11_format_based_semantics
from .rule_12_merged_cells import generate as generate_rule_12_merged_cells
from .rule_13_hidden_rows_columns import generate as generate_rule_13_hidden_rows_columns
from .rule_14_csv_single_line import generate as generate_rule_14_csv_single_line
from .rule_15_csv_quoting import generate as generate_rule_15_csv_quoting
from .rule_16_number_column import generate as generate_rule_16_number_column
from .rule_17_omit_column import generate as generate_rule_17_omit_column
from .rule_18_unique_column import generate as generate_rule_18_unique_column
from .rule_19_normalize_nominals import generate as generate_rule_19_normalize_nominals
from .rule_20_split_other import generate as generate_rule_20_split_other
from .rule_21_formula_convert_integer import generate as generate_rule_21_formula_convert_integer
from .rule_22_header_start_position import generate as generate_rule_22_header_start_position
from .rule_25_data_units import generate as generate_rule_25_data_units

RuleGenerator = Callable[[Path], list[Path]]

RULE_GENERATORS_BY_NUMBER: dict[int, RuleGenerator] = {
    1: generate_rule_01_file_format,
    2: generate_rule_02_multiple_tables,
    3: generate_rule_03_fragmented_data,
    4: generate_rule_04_extraneous_info,
    5: generate_rule_05_missing_column_names,
    6: generate_rule_06_space_formatting,
    7: generate_rule_07_one_cell_one_data,
    8: generate_rule_08_platform_dependent_chars,
    10: generate_rule_10_excel_objects,
    11: generate_rule_11_format_based_semantics,
    12: generate_rule_12_merged_cells,
    13: generate_rule_13_hidden_rows_columns,
    14: generate_rule_14_csv_single_line,
    15: generate_rule_15_csv_quoting,
    16: generate_rule_16_number_column,
    17: generate_rule_17_omit_column,
    18: generate_rule_18_unique_column,
    19: generate_rule_19_normalize_nominals,
    20: generate_rule_20_split_other,
    21: generate_rule_21_formula_convert_integer,
    22: generate_rule_22_header_start_position,
    25: generate_rule_25_data_units,
}

RULE_GENERATORS = [RULE_GENERATORS_BY_NUMBER[n] for n in sorted(RULE_GENERATORS_BY_NUMBER)]
