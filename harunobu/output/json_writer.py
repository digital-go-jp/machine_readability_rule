"""JSON出力ライター

AnalysisResult を日本語キーの JSON 形式に変換する。

スコアリングは ``harunobu.core.scorer.LevelScorer`` が責務として持つため、
出力時に Scorer を呼び出してレベル別スコアを埋め込む。総合評価点は出さない
（レベルごとの評価点のみ）。

出力形式:
{
  "inputファイル名": "...",
  "ファイルサイズ": 1024,
  "フォーマット": "xlsx",
  "Sheet数": 1,
  "レベル別スコア": {
    "1": {
      "スコア": 80, "合格": 4, "合計": 5, "強制0点": false,
      "強制0点ルール": [],
      "失敗ルール": [{"ルールID": "L1-03", "重大度": "critical"}]
    },
    "2": {
      "スコア": 0, "合格": 1, "合計": 3, "強制0点": true,
      "強制0点ルール": [{"ルールID": "L2-01", "重大度": "fatal"}],
      "失敗ルール": [...]
    },
    "3": null
  },
  "sheets": [
    {
      "シート名": "Sheet1",
      "使用範囲": "A1:E10",
      "非表示": false,
      "評価対象エリア": [
        {
          "範囲": "A1:E10",
          "信頼度": 0.95,
          "ヘッダー行": [1],
          "ヘッダー範囲": "A1:E1",
          "列数": 5,
          "評価内容": [
            {
              "ルールID": "L1-01",
              "合否": true,
              "重大度": "fatal",
              "信頼度": 1.0,
              "違反": [],
              "メッセージ": ""
            }
          ]
        }
      ]
    }
  ]
}
"""

from __future__ import annotations

import json
from typing import Any

from harunobu.core.models import AnalysisResult, CellRange, CheckResult, SheetResult, TableResult
from harunobu.core.scorer import LevelScore, LevelScorer
from harunobu.rules.base import RuleBase
from harunobu.rules.bulk_base import BulkAnalysisResult
from harunobu.rules.registry import registry


def _rule_meta(rule: RuleBase | None) -> tuple[str, str, str]:
    """ルールの名称・説明・原本説明を返す。rule が None なら空文字のタプル。"""
    if rule is None:
        return "", "", ""
    return rule.rule_name, rule.description, rule.original_description


def to_dict(result: AnalysisResult, *, include_original_description: bool = False) -> dict[str, Any]:
    """AnalysisResult を日本語キーの辞書に変換する。

    Args:
        result: 変換対象の解析結果。
        include_original_description: True の場合、各チェック結果にデジタル庁
            機械可読性チェックリスト原本の説明文（``原本説明``）を含める。
    """
    scoring = LevelScorer().score_analysis(result)
    return {
        "inputファイル名": result.file_meta.name,
        "ファイルサイズ": result.file_meta.size,
        "フォーマット": result.file_meta.format,
        "Sheet数": result.file_meta.sheet_count,
        "レベル別スコア": {str(level): _level_score_to_dict(scoring.per_level[level]) for level in (1, 2, 3)},
        "sheets": [_sheet_to_dict(s, include_original_description=include_original_description) for s in result.sheets],
    }


def to_json(result: AnalysisResult, *, indent: int = 2, include_original_description: bool = False) -> str:
    """AnalysisResult を JSON 文字列に変換する。"""
    return json.dumps(
        to_dict(result, include_original_description=include_original_description),
        ensure_ascii=False,
        indent=indent,
    )


def write_json(
    result: AnalysisResult, path: str, *, indent: int = 2, include_original_description: bool = False
) -> None:
    """AnalysisResult を JSON ファイルに書き出す。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            to_dict(result, include_original_description=include_original_description),
            f,
            ensure_ascii=False,
            indent=indent,
        )


def to_bulk_dict(bulk_result: BulkAnalysisResult, *, include_original_description: bool = False) -> dict[str, Any]:
    """BulkAnalysisResult を日本語キーの辞書に変換する。

    複数ファイル総合スコア・ファイル横断チェック結果に加え、各ファイルの結果を
    ``ファイル別結果`` に並べる。
    """
    per_file_scores = bulk_result.per_file_scores()
    return {
        "複数ファイル総合スコア": bulk_result.total_score,
        "ファイル数": bulk_result.file_count,
        "ファイル横断チェック": {
            rule_id: _check_to_dict(rule_id, cr, include_original_description=include_original_description)
            for rule_id, cr in bulk_result.bulk_checks.items()
        },
        "ファイル別平均スコア": [
            {"ファイル名": r.file_meta.name, "平均スコア": s}
            for r, s in zip(bulk_result.files, per_file_scores, strict=True)
        ],
        "ファイル別結果": [
            to_dict(r, include_original_description=include_original_description) for r in bulk_result.files
        ],
    }


def to_bulk_json(
    bulk_result: BulkAnalysisResult, *, indent: int = 2, include_original_description: bool = False
) -> str:
    """BulkAnalysisResult を JSON 文字列に変換する。"""
    return json.dumps(
        to_bulk_dict(bulk_result, include_original_description=include_original_description),
        ensure_ascii=False,
        indent=indent,
    )


def _level_score_to_dict(ls: LevelScore) -> dict[str, Any] | None:
    """LevelScore を日本語キーの辞書に変換。score が None なら null（未チェック）。"""
    if ls.score is None:
        return None
    return {
        "スコア": ls.score,
        "合格": ls.passed,
        "合計": ls.total,
        "強制0点": ls.forced_zero,
        "強制0点ルール": [_failed_rule_to_dict(fr.rule_id, fr.severity.value) for fr in ls.forced_zero_rules],
        "失敗ルール": [_failed_rule_to_dict(fr.rule_id, fr.severity.value) for fr in ls.failed_rules],
    }


def _failed_rule_to_dict(rule_id: str, severity: str) -> dict[str, Any]:
    """失敗ルール／強制0点ルールのサマリーエントリを辞書に変換。"""
    rule_name, _, _ = _rule_meta(registry.get_or_none(rule_id))
    return {
        "ルールID": rule_id,
        "ルール名": rule_name,
        "重大度": severity,
    }


def _sheet_to_dict(sheet_result: SheetResult, *, include_original_description: bool) -> dict[str, Any]:
    """シート結果を辞書に変換。"""
    d: dict[str, Any] = {
        "シート名": sheet_result.sheet_meta.name,
        "使用範囲": sheet_result.sheet_meta.used_range,
        "非表示": sheet_result.sheet_meta.hidden,
        "評価対象エリア": [
            _table_to_dict(t, include_original_description=include_original_description) for t in sheet_result.tables
        ],
    }

    if sheet_result.sheet_property:
        sp = sheet_result.sheet_property
        d["sheetProperty"] = {
            "sheetName": sp.sheet_name,
            "maxRow": sp.max_row,
            "maxCol": sp.max_col,
            "hidden": sp.hidden,
        }

    if sheet_result.others:
        d["others"] = [
            {
                "row": o.row,
                "col": o.col,
                "value": o.value,
                "regionType": o.region_type,
            }
            for o in sheet_result.others
        ]

    return d


def _table_to_dict(table_result: TableResult, *, include_original_description: bool) -> dict[str, Any]:
    """テーブル結果を辞書に変換。"""
    d: dict[str, Any] = {
        "範囲": str(table_result.range),
        "信頼度": table_result.confidence,
        "ヘッダー行": table_result.layout.header_rows,
        "ヘッダー範囲": _header_range(table_result),
        "列数": table_result.range.end_col - table_result.range.start_col + 1,
        "評価内容": [
            _check_to_dict(rule_id, cr, include_original_description=include_original_description)
            for rule_id, cr in table_result.mr_result.all_results().items()
        ],
    }

    if table_result.column_headers:
        d["columnHeaders"] = [
            {
                "colIndex": ch.col_index,
                "headerRows": ch.header_rows,
                "label": ch.label,
                "isMerged": ch.is_merged,
            }
            for ch in table_result.column_headers
        ]

    if table_result.columns:
        d["columns"] = [
            {
                "colIndex": cs.col_index,
                "inferredType": cs.inferred_type,
                "hasHeader": cs.has_header,
            }
            for cs in table_result.columns
        ]

    return d


def _header_range(table_result: TableResult) -> str | None:
    """ヘッダー行が占めるセル領域を ``A1:E1`` 形式で返す。ヘッダー未検出なら None。"""
    header_rows = table_result.layout.header_rows
    if not header_rows:
        return None
    return str(
        CellRange(
            start_row=min(header_rows),
            start_col=table_result.range.start_col,
            end_row=max(header_rows),
            end_col=table_result.range.end_col,
        )
    )


def _check_to_dict(rule_id: str, check_result: CheckResult, *, include_original_description: bool) -> dict[str, Any]:
    """チェック結果を辞書に変換。"""
    rule_name, description, original_description = _rule_meta(registry.get_or_none(rule_id))
    result: dict[str, Any] = {
        "ルールID": rule_id,
        "ルール名": rule_name,
        "ルール説明": description,
        "合否": check_result.passed,
        "判定対象外": check_result.is_skipped,
        "重大度": check_result.effective_severity.value,
        "信頼度": check_result.confidence,
    }
    if include_original_description:
        result["原本説明"] = original_description

    # 「違反」は常に生の Violation リスト（後方互換性を保つ）
    result["違反"] = [
        {
            "シート": v.sheet,
            "セル範囲": v.cell_range,
            "説明": v.description,
            "違反重大度": v.severity,
        }
        for v in check_result.violations
    ]

    # 閾値超過時は「違反グループ」フィールドで (sheet, severity) 集計を追加
    if check_result.is_display_truncated:
        result["違反グループ"] = {
            "合計件数": len(check_result.violations),
            "グループ": [
                {
                    "シート": g.sheet,
                    "重大度": g.severity,
                    "件数": g.count,
                    "代表セル範囲": [v.cell_range for v in g.samples],
                }
                for g in check_result.violation_groups
            ],
        }

    result["メッセージ"] = check_result.message

    return result
