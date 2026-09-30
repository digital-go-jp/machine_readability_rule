"""CSV出力ライター

AnalysisResult を CSV 行に変換する。

出力カラム:
ファイル名, シート名, テーブル範囲, ヘッダー範囲, 列数, ルールID, ルール名, ルール説明,
(原本説明), 合否, 判定対象外, 重大度, 信頼度, 違反数, 違反箇所, 違反内容, 違反重大度, メッセージ

- 「重大度」はルール失敗の severity（fatal/critical/major/minor/info）
- 「違反重大度」はセル単位の violation severity（error/warning/info）
- 「判定対象外」は confidence=0 のルールに「○」を出力
- 「ヘッダー範囲」はヘッダー行が占めるセル領域（``A1:E1`` 形式）。未検出なら空文字
- 「列数」はテーブルの列数（項目数）
- 「ルール説明」は実装が何を検査しているかの短い説明、「原本説明」はデジタル庁
  機械可読性チェックリスト原本の説明文（``RuleBase.description`` / ``RuleBase.original_description``）。
  「原本説明」は ``include_original_description=True`` を指定した場合のみ「ルール説明」の直後に追加される
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from harunobu.core.models import AnalysisResult, CellRange, TableResult
from harunobu.rules.base import RuleBase
from harunobu.rules.bulk_base import BulkAnalysisResult
from harunobu.rules.registry import registry

# CSV ヘッダー（既定。原本説明は --with-original-description 指定時のみ追加される）
HEADER = [
    "ファイル名",
    "シート名",
    "テーブル範囲",
    "ヘッダー範囲",
    "列数",
    "ルールID",
    "ルール名",
    "ルール説明",
    "合否",
    "判定対象外",
    "重大度",
    "信頼度",
    "違反数",
    "違反箇所",
    "違反内容",
    "違反重大度",
    "メッセージ",
]


def _header(*, include_original_description: bool) -> list[str]:
    """CSV ヘッダーを返す。include_original_description が True なら「ルール説明」の直後に「原本説明」を挿入する。"""
    if not include_original_description:
        return HEADER
    idx = HEADER.index("ルール説明") + 1
    return HEADER[:idx] + ["原本説明"] + HEADER[idx:]


def _rule_meta(rule: RuleBase | None) -> tuple[str, str, str]:
    """ルールの名称・説明・原本説明を返す。rule が None なら空文字のタプル。"""
    if rule is None:
        return "", "", ""
    return rule.rule_name, rule.description, rule.original_description


def _header_range(table: TableResult) -> str:
    header_rows = table.layout.header_rows
    if not header_rows:
        return ""
    return str(
        CellRange(
            start_row=min(header_rows),
            start_col=table.range.start_col,
            end_row=max(header_rows),
            end_col=table.range.end_col,
        )
    )


def to_rows(result: AnalysisResult, *, include_original_description: bool = False) -> list[list[str]]:
    """AnalysisResult を CSV 行リストに変換する。

    Returns:
        list[list[str]]: ヘッダー行 + データ行
    """
    rows: list[list[str]] = [_header(include_original_description=include_original_description)]

    for sheet_result in result.sheets:
        sheet_name = sheet_result.sheet_meta.name
        for table in sheet_result.tables:
            table_range = str(table.range)
            header_range = _header_range(table)
            column_count = str(table.range.end_col - table.range.start_col + 1)
            for rule_id, check_result in table.mr_result.all_results().items():
                rule_name, description, original_description = _rule_meta(registry.get_or_none(rule_id))
                if check_result.is_display_truncated:
                    groups = check_result.violation_groups
                    sample_locs = "; ".join(f"{v.sheet}!{v.cell_range}" for v in check_result.violations[:3])
                    violation_locs = f"{sample_locs} 他（計 {len(check_result.violations)} 件）"
                    violation_descs = "; ".join(f"{g.sheet}/{g.severity}: {g.count}件" for g in groups)
                    violation_severities = "; ".join(f"{g.severity}: {g.count}件" for g in groups)
                else:
                    violation_locs = "; ".join(f"{v.sheet}!{v.cell_range}" for v in check_result.violations)
                    violation_descs = "; ".join(v.description for v in check_result.violations)
                    violation_severities = "; ".join(v.severity for v in check_result.violations)
                row = [
                    result.file_meta.name,
                    sheet_name,
                    table_range,
                    header_range,
                    column_count,
                    rule_id,
                    rule_name,
                    description,
                ]
                if include_original_description:
                    row.append(original_description)
                row += [
                    "合格" if check_result.passed else "不合格",
                    "○" if check_result.is_skipped else "",
                    check_result.effective_severity.value,
                    f"{check_result.confidence:.2f}",
                    str(len(check_result.violations)),
                    violation_locs,
                    violation_descs,
                    violation_severities,
                    check_result.message,
                ]
                rows.append(row)

    return rows


def to_csv_string(result: AnalysisResult, *, include_original_description: bool = False) -> str:
    """AnalysisResult を CSV 文字列に変換する。"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(to_rows(result, include_original_description=include_original_description))
    return output.getvalue()


def write_csv(result: AnalysisResult, path: str | Path, *, include_original_description: bool = False) -> None:
    """AnalysisResult を CSV ファイルに書き出す。"""
    path = Path(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(to_rows(result, include_original_description=include_original_description))


def to_bulk_rows(bulk_result: BulkAnalysisResult, *, include_original_description: bool = False) -> list[list[str]]:
    """BulkAnalysisResult を CSV 行リストに変換する。

    出力は単一ファイル CSV と同じ列構成だが、各ファイルの行に加えて
    末尾にファイル横断チェック結果を ``ファイル名="(bulk)"`` として連結する。
    """
    rows: list[list[str]] = [_header(include_original_description=include_original_description)]
    for analysis in bulk_result.files:
        # 各ファイルの行を追加（ヘッダー行は除外）
        rows.extend(to_rows(analysis, include_original_description=include_original_description)[1:])

    for rule_id, cr in bulk_result.bulk_checks.items():
        rule_name, description, original_description = _rule_meta(registry.get_or_none(rule_id))
        violation_locs = "; ".join(f"{v.sheet}!{v.cell_range}" for v in cr.violations)
        violation_descs = "; ".join(v.description for v in cr.violations)
        violation_severities = "; ".join(v.severity for v in cr.violations)
        row = [
            "(bulk)",
            "",
            "",
            "",
            "",
            rule_id,
            rule_name,
            description,
        ]
        if include_original_description:
            row.append(original_description)
        row += [
            "合格" if cr.passed else "不合格",
            "○" if cr.is_skipped else "",
            cr.effective_severity.value,
            f"{cr.confidence:.2f}",
            str(len(cr.violations)),
            violation_locs,
            violation_descs,
            violation_severities,
            cr.message,
        ]
        rows.append(row)
    return rows


def to_bulk_csv_string(bulk_result: BulkAnalysisResult, *, include_original_description: bool = False) -> str:
    """BulkAnalysisResult を CSV 文字列に変換する。"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(to_bulk_rows(bulk_result, include_original_description=include_original_description))
    return output.getvalue()
