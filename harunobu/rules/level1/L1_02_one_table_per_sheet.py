"""L1-02: 1シートに1表のみかチェック"""

from __future__ import annotations

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class OneTablePerSheetRule(RuleBase):
    """1シートに1つの表のみが含まれていることを確認する。"""

    rule_id = "L1-02"
    rule_name = "１シート（ファイル）に複数の表が掲載されていないか"
    level = 1
    target = TargetFormat.COMMON
    description = "1シートに1つの表のみが含まれていることを確認します。"

    severity = Severity.FATAL

    def _get_tables(self, context: TableContext) -> list:
        """シート上のテーブル一覧を取得する（キャッシュ優先）。"""
        if context.all_tables:
            return context.all_tables
        from harunobu.core.layout.detector import LayoutDetector

        detector = LayoutDetector(context.config)
        return detector.detect(context.sheet)

    def check(self, context: TableContext) -> CheckResult:
        """1 シートに含まれる表が 1 つだけかを検査する。"""
        all_tables = self._get_tables(context)
        # 低信頼度のテーブル（タイトル行、注釈ブロック等）を除外
        tables = [t for t in all_tables if getattr(t, "confidence", 1.0) >= 0.5]
        if not tables:
            tables = all_tables  # フォールバック: 全て低信頼度なら全て使う
        table_count = len(tables)

        if table_count <= 1:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.85,
                message="1シートに1表のみです。",
            )

        # 複数テーブルが検出された場合、最初のテーブルでのみ違反を報告
        current_range = context.table_region.range
        first_table_range = tables[0].range if tables else None

        is_first_table = first_table_range is not None and (
            current_range.start_row == first_table_range.start_row
            and current_range.start_col == first_table_range.start_col
        )

        if not is_first_table:
            # 最初のテーブルでのみ報告するので、2番目以降はパス扱い
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.85,
                message="（別テーブルで報告済み）",
            )

        violations = [
            Violation(
                sheet=context.sheet.name,
                cell_range=str(t.range),
                description=f"テーブルが{t.range}に検出されました。",
                severity="warning",
            )
            for t in tables
        ]
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=0.85,
            violations=violations,
            message=(
                f"シート '{context.sheet.name}' に{table_count}個の"
                "テーブルが検出されました。1シートに1表のみにしてください。"
            ),
        )
