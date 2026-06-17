"""L3-07: 年によってフォーマットが著しく異なっていないか"""

from __future__ import annotations

import statistics

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat
from harunobu.rules.bulk_base import BulkFileEntry, BulkRuleMixin


class FormatConsistencyRule(RuleBase, BulkRuleMixin):
    """複数ファイル横断でフォーマットの一貫性が保たれているかを検査する。

    同一データセットの各年版で項目名・列数・列順序が一貫しているかを確認する。
    単一ファイルの場合は判定対象外（check_bulk のみで評価）。
    """

    rule_id = "L3-07"
    rule_name = "年によってフォーマットが著しく異なっていないか"
    level = 3
    target = TargetFormat.COMMON
    description = (
        "同一データセットの各年版において、項目名・列数・列順序などのフォーマットが年ごとに異なっていないか確認します。"
    )

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """単一ファイル評価では判定対象外。複数ファイル一括時のみ check_bulk で評価する。"""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            confidence=0,
            violations=[],
            message="複数ファイル一括アップロード時のみ評価対象（単一ファイルでは判定しない）",
        )

    def check_bulk(self, files: list[BulkFileEntry]) -> CheckResult:
        """複数ファイル横断のフォーマット一貫性チェック.

        年版違いの Excel ファイルが並んだ際に、項目名・列数・列順序が
        変動していないかを確認する。
        """
        if len(files) < 2:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.5,
                violations=[],
                message="bulk評価対象が1ファイル以下のためスキップ",
            )

        # 各ファイルの「トップテーブル」（最初のシートの最初のテーブル）のヘッダー列を抽出
        per_file_headers: list[tuple[str, list[str]]] = []
        for entry in files:
            headers = _extract_top_table_headers(entry)
            per_file_headers.append((entry.file_name, headers))

        violations: list[Violation] = []

        # ヘッダー抽出に失敗したファイルを明示的に報告する。
        # silently drop すると「1ファイルだけ抽出失敗・他が一致」のときに
        # 誤って「一貫性あり」と判定してしまうため、warning として可視化する。
        missing = [name for name, h in per_file_headers if not h]
        if missing:
            violations.append(
                Violation(
                    sheet="(bulk)",
                    cell_range="",
                    description=(
                        f"以下のファイルからヘッダーを抽出できなかったため、フォーマット一貫性評価から除外しています: "
                        f"{', '.join(missing)}。"
                        f"ヘッダー行が認識できるよう構造を見直してください。"
                    ),
                    severity="warning",
                )
            )

        # ヘッダー抽出に成功したファイルが 2 件未満なら、それ以降の集合比較は意味が無いため早期 return。
        evaluable = [(name, h) for name, h in per_file_headers if h]
        if len(evaluable) < 2:
            passed = len(violations) == 0
            return CheckResult(
                rule_id=self.rule_id,
                passed=passed,
                confidence=0.5,
                violations=violations,
                message=(
                    "ヘッダー抽出可能なファイルが 2 件未満のため、ファイル横断の一貫性評価をスキップしました"
                    if violations
                    else "評価対象が不足しているためスキップ"
                ),
            )

        # 1. ヘッダー集合の Jaccard 類似度
        all_headers = [set(h) for _, h in evaluable]
        jaccard = _min_pairwise_jaccard(all_headers)
        if jaccard < 0.8:
            violations.append(
                Violation(
                    sheet="(bulk)",
                    cell_range="",
                    description=(
                        f"ファイル間でヘッダー集合が大きく異なります（Jaccard類似度 {jaccard:.2f} < 0.8）。"
                        f"対象ファイル: {', '.join(name for name, _ in evaluable)}"
                    ),
                    severity="warning",
                )
            )

        # 2. 列数のばらつき
        col_counts = [len(h) for _, h in evaluable]
        stdev = statistics.pstdev(col_counts)
        if stdev > 1.5:
            violations.append(
                Violation(
                    sheet="(bulk)",
                    cell_range="",
                    description=(f"ファイル間で列数が変動しています（標準偏差 {stdev:.2f}, 列数: {col_counts}）"),
                    severity="warning",
                )
            )

        # 3. 列順序の差異（共通ヘッダーが両ファイルで同じ順序か）
        order_changed = _check_order_change(evaluable)
        if order_changed:
            violations.append(
                Violation(
                    sheet="(bulk)",
                    cell_range="",
                    description=(
                        "ファイル間で共通ヘッダーの並び順が変動しています。"
                        "時系列での自動結合・比較に支障が出る可能性があります"
                    ),
                    severity="info",
                )
            )

        passed = len(violations) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=0.8,
            violations=violations,
            message=(
                f"複数ファイル間のフォーマット不整合: {len(violations)}件検出"
                if violations
                else f"{len(files)}ファイル間でフォーマットの一貫性が保たれています"
            ),
        )


def _extract_top_table_headers(entry: BulkFileEntry) -> list[str]:
    """エントリの最初のシートの最初のテーブルからヘッダー名を抽出する."""
    for sheet_result in entry.analysis.sheets:
        for table in sheet_result.tables:
            if table.column_headers:
                labels = [h.label.strip() for h in table.column_headers if h.label]
                if labels:
                    return labels
    return []


def _min_pairwise_jaccard(sets: list[set[str]]) -> float:
    """全ペアの Jaccard 類似度の最小値を返す."""
    min_jaccard = 1.0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = sets[i] | sets[j]
            if not union:
                continue
            jaccard = len(sets[i] & sets[j]) / len(union)
            if jaccard < min_jaccard:
                min_jaccard = jaccard
    return min_jaccard


def _check_order_change(per_file_headers: list[tuple[str, list[str]]]) -> bool:
    """共通ヘッダーの並び順が変動しているか判定する."""
    if len(per_file_headers) < 2:
        return False
    common = set(per_file_headers[0][1])
    for _, headers in per_file_headers[1:]:
        common &= set(headers)
    if len(common) < 2:
        return False

    reference_order: list[str] | None = None
    for _, headers in per_file_headers:
        filtered = [h for h in headers if h in common]
        if reference_order is None:
            reference_order = filtered
        elif filtered != reference_order:
            return True
    return False
