"""Analyzer / MRChecker — メインパイプラインオーケストレータ

公開 API:
- Analyzer(mode) — UI 向けクラス
- analyze(path, config) -> AnalysisResult
- analyze_sheet(sheet, config) -> SheetResult
"""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import IO

from harunobu.core.layout.detector import LayoutDetector
from harunobu.core.models import (
    AnalysisResult,
    CheckResult,
    Config,
    FileMeta,
    MRResult,
    Sheet,
    SheetMeta,
    SheetProperty,
    SheetResult,
    TableContext,
    TableResult,
    WorkBook,
)
from harunobu.core.reader import read_file
from harunobu.rules.base import TargetFormat
from harunobu.rules.bulk_base import BulkAnalysisResult, BulkFileEntry, BulkRuleMixin
from harunobu.rules.registry import RuleRegistry, registry

logger = logging.getLogger(__name__)

# ルール並列実行の最大ワーカー数（I/O バウンドな AI API 呼出に最適化）
_MAX_CHECK_WORKERS = 8


class Analyzer:
    """モード指定つきの分析クラス。UI から呼び出す際に使用する。"""

    def __init__(self, mode: str = "standard") -> None:
        # mr_levels は Config が mode から導出する（models.py の _MODE_LEVELS が
        # 単一の真実の源）。ファイルベースの analyze(path, Config(mode=...)) と
        # 同じ経路を通すことで、両者が必ず同じレベル集合を評価するようにする。
        self._config = Config(mode=mode)  # type: ignore[arg-type]

    def analyze(self, workbook: WorkBook) -> AnalysisResult:
        """WorkBook を分析して AnalysisResult を返す。"""
        sheet_results: list[SheetResult] = []
        for sheet in workbook.sheets:
            sheet_result = analyze_sheet(workbook=workbook, sheet=sheet, config=self._config)
            sheet_results.append(sheet_result)

        return AnalysisResult(
            file_meta=FileMeta(
                name=workbook.file_name,
                size=workbook.file_size,
                format=workbook.file_format,
                sheet_count=len(workbook.sheets),
            ),
            sheets=sheet_results,
        )

    def analyze_file(self, file_name: str, file_bytes: IO[bytes]) -> AnalysisResult:
        """ファイル名とバイトストリームを受け取り分析する。"""
        from harunobu.core.reader import read_workbook

        workbook = read_workbook(file_name, file_bytes)
        return self.analyze(workbook)

    def analyze_bulk(self, workbooks: list[WorkBook]) -> BulkAnalysisResult:
        """複数 WorkBook を一括分析し、ファイル横断チェックも実行する。

        Phase 1: 各ファイルを個別に analyze() で評価
        Phase 2: BulkRuleMixin を継承したルールを検出し、ファイル横断 check_bulk() を呼び出す

        ファイルが 1 つだけの場合は Phase 2 をスキップする。
        """
        per_file_results: list[AnalysisResult] = []
        entries: list[BulkFileEntry] = []
        for wb in workbooks:
            result = self.analyze(wb)
            per_file_results.append(result)
            entries.append(
                BulkFileEntry(
                    file_name=wb.file_name,
                    file_meta=result.file_meta,
                    workbook=wb,
                    analysis=result,
                )
            )

        bulk_checks: dict[str, CheckResult] = {}
        if len(entries) >= 2:
            bulk_checks = _run_bulk_rules(entries, self._config)

        return BulkAnalysisResult(
            files=per_file_results,
            bulk_checks=bulk_checks,
        )


def _run_bulk_rules(
    entries: list[BulkFileEntry],
    config: Config,
) -> dict[str, CheckResult]:
    """登録済みルールのうち BulkRuleMixin を持つものに対して check_bulk を実行する。

    複数ファイルアップロードはユーザーがファイル横断評価を明示的に要求した状況なので、
    ``config.mr_levels`` によるフィルタリングは行わない。``mr_levels`` は単一ファイル
    評価の深さを制御するものであり、bulk ルールの実行可否は別軸として扱う。
    """
    if not registry.get_all():
        registry.discover()

    results: dict[str, CheckResult] = {}
    for rule in registry.get_all():
        if not isinstance(rule, BulkRuleMixin):
            continue
        try:
            result = rule.check_bulk(entries)
        except Exception as exc:
            if config.strict:
                raise
            logger.error(
                "bulkルール %s の check_bulk でエラー: %s: %s",
                rule.rule_id,
                type(exc).__name__,
                exc,
            )
            result = CheckResult(
                rule_id=rule.rule_id,
                passed=True,
                score=0,
                confidence=0.0,
                message=f"bulkルール {rule.rule_id} の実行中にエラー: {type(exc).__name__}: {exc}",
            )
        results[rule.rule_id] = result
    return results


class MRChecker:
    """機械可読性チェッカー。

    RuleRegistry から対象ルールを取得し、一括で check を実行する。
    """

    def __init__(self, rule_registry: RuleRegistry | None = None) -> None:
        self._registry = rule_registry or registry

    def check_all(self, context: TableContext, config: Config) -> MRResult:
        """全対象ルールの check を実行し MRResult を返す。

        Args:
            context (TableContext): チェック対象のコンテキスト
            config (Config): 設定

        Returns:
            MRResult
        """
        # ルール発見がまだなら実行
        if not self._registry.get_all():
            self._registry.discover()

        # ファイル形式に応じたターゲット
        target = _file_format_to_target(context.workbook.file_format)

        result = MRResult()

        # 実行対象ルールを収集
        tasks: list[tuple[int, object]] = []
        for level in sorted(config.mr_levels):
            rules = self._registry.get_by_level(level)
            for rule in rules:
                if rule.target not in (target, TargetFormat.COMMON):
                    continue
                if config.custom_rules and rule.rule_id not in config.custom_rules:
                    continue
                tasks.append((level, rule))

        def _run_rule(level: int, rule: object) -> tuple[int, str, CheckResult]:
            try:
                check_result = rule.check(context)
            except Exception as exc:
                if config.strict:
                    raise
                tb = traceback.format_exc()
                logger.error(
                    "ルール %s の check でエラー: %s: %s\n%s",
                    rule.rule_id,
                    type(exc).__name__,
                    exc,
                    tb,
                )
                check_result = CheckResult(
                    rule_id=rule.rule_id,
                    passed=True,
                    severity=rule.severity,
                    confidence=0.0,
                    message=f"ルール {rule.rule_id} の実行中にエラーが発生しました: {type(exc).__name__}: {exc}",
                )
            # ルールが check() 内で severity を明示的に設定した場合はそれを尊重する。
            # 未設定のときだけクラス属性 (rule.severity) で注入する。
            # これにより、L1-12 のように条件次第で severity を変えるルールが書ける。
            if check_result.severity is None:
                check_result.severity = rule.severity
            return (level, rule.rule_id, check_result)

        # スレッドプールで並列実行（I/O バウンドな AI API 呼び出しに効果的）
        max_workers = min(len(tasks), _MAX_CHECK_WORKERS) if tasks else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_run_rule, level, rule): (level, rule) for level, rule in tasks}
            for future in as_completed(futures):
                level, rule_id, check_result = future.result()
                level_dict = {
                    1: result.level1,
                    2: result.level2,
                    3: result.level3,
                }.get(level)
                if level_dict is not None:
                    level_dict[rule_id] = check_result

        return result


def analyze(path: str | Path, config: Config | None = None) -> AnalysisResult:
    """ファイルを読み込み、採点結果を返す。

    Args:
        path (str | Path): 対象ファイルパス
        config (Config | None): 設定（省略時はデフォルト）

    Returns:
        AnalysisResult
    """
    config = config or Config()
    path = Path(path)

    # ファイル読み込み
    workbook = read_file(path)

    # シートごとに分析
    sheet_results: list[SheetResult] = []
    for sheet in workbook.sheets:
        sheet_result = analyze_sheet(
            workbook=workbook,
            sheet=sheet,
            config=config,
        )
        sheet_results.append(sheet_result)

    return AnalysisResult(
        file_meta=FileMeta(
            name=workbook.file_name,
            size=workbook.file_size,
            format=workbook.file_format,
            sheet_count=len(workbook.sheets),
        ),
        sheets=sheet_results,
    )


def analyze_sheet(
    *,
    workbook: WorkBook | None = None,
    sheet: Sheet,
    config: Config | None = None,
) -> SheetResult:
    """シート単位の分析を行う。

    Args:
        workbook (WorkBook | None): ワークブック（None の場合はダミーを生成）
        sheet (Sheet): 対象シート
        config (Config | None): 設定

    Returns:
        SheetResult
    """
    config = config or Config()

    if workbook is None:
        workbook = WorkBook(
            file_name="unknown",
            file_format="xlsx",
            sheets=[sheet],
        )

    # レイアウト検出
    detector = LayoutDetector(config)
    detection = detector.detect_with_others(sheet)
    table_regions = detection.tables
    sheet_others = detection.others

    # MRチェック
    checker = MRChecker()
    table_results: list[TableResult] = []

    for region in table_regions:
        context = TableContext(
            workbook=workbook,
            sheet=sheet,
            table_region=region,
            config=config,
            all_tables=table_regions,
            sheet_others=sheet_others,
        )

        mr_result = checker.check_all(context, config)

        table_results.append(
            TableResult(
                range=region.range,
                layout=region.layout,
                confidence=region.confidence,
                mr_result=mr_result,
                column_headers=region.layout.column_headers,
                columns=region.layout.columns,
            )
        )

    # シートメタ
    used_range = ""
    if sheet.max_row > 0 and sheet.max_col > 0:
        from harunobu.core.models import CellPosition

        start = CellPosition(row=1, col=1)
        end = CellPosition(row=sheet.max_row, col=sheet.max_col)
        used_range = f"{start}:{end}"

    return SheetResult(
        sheet_meta=SheetMeta(
            name=sheet.name,
            used_range=used_range,
            hidden=sheet.hidden,
        ),
        tables=table_results,
        sheet_property=SheetProperty(
            sheet_name=sheet.name,
            max_row=sheet.max_row,
            max_col=sheet.max_col,
            hidden=sheet.hidden,
        ),
        others=sheet_others,
    )


def _file_format_to_target(file_format: str) -> TargetFormat:
    """ファイル形式を TargetFormat に変換する。"""
    if file_format == "xlsx":
        return TargetFormat.EXCEL
    elif file_format in ("csv", "tsv"):
        return TargetFormat.CSV
    return TargetFormat.COMMON
