"""L1-05: 列ヘッダーの存在チェック

ヘッダー領域のセル結合は L1-12 が許容する方針と整合し、本ルールでは結合マスタの値で
ヘッダーが設定されているとみなす。複数行ヘッダーで親行が横結合されているケースの
一意識別性は L2-03 で評価される。
"""

from __future__ import annotations

from harunobu.core.models import (
    CellPosition,
    CellRange,
    CheckResult,
    MergedRange,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

try:
    from harunobu.core.ai_visual_analyzer import AIVisualAnalyzer
except ImportError:
    AIVisualAnalyzer = None  # type: ignore[assignment, misc]

try:
    from harunobu.core.ai_semantic_checker import AISemanticChecker
except ImportError:
    AISemanticChecker = None  # type: ignore[assignment, misc]


class ColumnHeadersRule(RuleBase):
    """各列にヘッダーが設定されていることを確認する。"""

    rule_id = "L1-05"
    rule_name = "すべての列に意味が推測できる項目名が存在するか"
    level = 1
    target = TargetFormat.COMMON
    description = "テーブルの各列にヘッダー（列名）が設定されていることを確認します。"

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """データのある各列にヘッダー（列名）が設定されているかを検査する。"""
        sheet = context.sheet
        region = context.table_region.range
        layout = context.table_region.layout
        violations: list[Violation] = []

        # ヘッダー行が特定されている場合、そのヘッダー行を使う
        header_rows = layout.header_rows
        if not header_rows:
            # ヘッダー行が未特定の場合、テーブル領域の先頭行をヘッダーとみなす
            header_rows = [region.start_row]

        # ボディ行の範囲を特定
        body_start = layout.body_start_row
        body_end = layout.body_end_row

        # ヘッダー行にある結合セル情報を収集し、結合でカバーされる列を特定。
        # L1-12 ではヘッダー領域のセル結合を許容（info Violation のみで pass）するため、
        # L1-05 でも結合のマスター値を全カバー列のヘッダーとして展開し「ヘッダー有り」とみなす。
        # 結合ヘッダー自体の良し悪しは L2-03（一意な項目名）で評価される。
        covered_by_merge: set[int] = set()
        for merged in sheet.merged_cells:
            # ヘッダー行と重なる結合セル、またはヘッダー行を跨ぐ結合セル
            if self._merge_overlaps_header(merged, header_rows):
                master_val = sheet.get_cell_value(merged.start_row, merged.start_col)
                if master_val is not None and str(master_val).strip() != "":
                    for c in range(merged.start_col, merged.end_col + 1):
                        covered_by_merge.add(c)
            # ヘッダー行より上から始まりヘッダー行以降まで伸びる縦方向の結合
            elif header_rows and merged.start_row < header_rows[0] and merged.end_row >= header_rows[0]:
                master_val = sheet.get_cell_value(merged.start_row, merged.start_col)
                if master_val is not None and str(master_val).strip() != "":
                    for c in range(merged.start_col, merged.end_col + 1):
                        covered_by_merge.add(c)

        # 各列のヘッダーが空白でないかチェック
        checked_cols = 0
        for c in range(region.start_col, region.end_col + 1):
            # 結合セルでカバーされている列はスキップ
            if c in covered_by_merge:
                checked_cols += 1
                continue

            # ボディ行にデータがあるか確認（データのない列はスキップ）
            has_body_data = False
            for r in range(body_start, body_end + 1):
                val = sheet.get_cell_value(r, c)
                if val is not None and str(val).strip() != "":
                    has_body_data = True
                    break

            if not has_body_data:
                # ヘッダーもデータもない列 → 違反としない
                # ヘッダーはあるがデータがない列 → 違反としない（空列）
                continue

            # データがある列はチェック対象としてカウント
            checked_cols += 1

            # ヘッダー行のいずれかに値があるか
            has_header = False
            for hr in header_rows:
                val = sheet.get_cell_value(hr, c)
                if val is not None and str(val).strip() != "":
                    has_header = True
                    break

            if not has_header:
                pos = CellPosition(row=header_rows[0], col=c)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=str(pos),
                        description=f"列{c}（{pos}）にヘッダーがありません。",
                        severity="error",
                    )
                )

        # ヘッダーが連番数値のみの場合、実質的にヘッダーが設定されていないとみなす
        sequential_violations = self._check_sequential_numeric_headers(context, header_rows, region)
        violations.extend(sequential_violations)

        # ビジュアル分析によるヘッダー構造の補完
        confidence_pass = 0.80
        confidence_fail = 0.85
        if AIVisualAnalyzer is not None and context.workbook.file_path:
            try:
                visual = AIVisualAnalyzer.get_instance()
                if visual.is_available():
                    header_info = visual.check_header_clarity(
                        context.workbook.file_path,
                        context.sheet.name,
                    )
                    # ビジュアルから複数行ヘッダーの結合問題を検出
                    for issue in header_info.get("issues", []):
                        desc = issue.get("description", "")
                        loc = issue.get("location", "")
                        if desc and loc:
                            violations.append(
                                Violation(
                                    sheet=sheet.name,
                                    cell_range=loc,
                                    description=f"ビジュアル分析: {desc}",
                                    severity="info",
                                )
                            )
                    confidence_pass = 0.85
                    confidence_fail = 0.90
            except Exception:
                pass

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=confidence_pass,
                message="すべての列にヘッダーが設定されています。",
            )

        max(checked_cols, 1)
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=confidence_fail,
            violations=violations,
            message=f"{len(violations)}列でヘッダーが欠落しています。",
        )

    @staticmethod
    def _check_sequential_numeric_headers(
        context: TableContext,
        header_rows: list[int],
        region: CellRange,
    ) -> list[Violation]:
        """ヘッダーが全て数値にキャストでき、かつ連番の場合に違反を返す。

        例: ヘッダーが '001', '002', '003' や 1, 2, 3 のように
        連番の数値のみで構成されている場合、実質的にヘッダーが未設定とみなす。
        """
        sheet = context.sheet

        # 各ヘッダー行から列ごとの値を収集
        # 複数ヘッダー行がある場合は最終ヘッダー行を使用
        hr = header_rows[-1]
        values: list[tuple[int, str]] = []
        for c in range(region.start_col, region.end_col + 1):
            val = sheet.get_cell_value(hr, c)
            if val is None or str(val).strip() == "":
                return []  # 空ヘッダーがある場合は別のチェックで検出済み
            values.append((c, str(val).strip()))

        if len(values) < 2:
            return []

        # 全て数値にキャストできるか
        nums: list[float] = []
        for _, v in values:
            try:
                nums.append(float(v))
            except ValueError:
                return []  # 数値でないヘッダーが1つでもあれば問題なし

        # 全て整数値で連番か（公差1の等差数列）
        if not all(n == int(n) for n in nums):
            return []

        int_nums = [int(n) for n in nums]
        is_sequential = all(int_nums[i + 1] - int_nums[i] == 1 for i in range(len(int_nums) - 1))
        if not is_sequential:
            return []

        # 連番数値ヘッダーを検出 → 全列に対して違反を生成
        violations = []
        for c, v in values:
            pos = CellPosition(row=hr, col=c)
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=str(pos),
                    description=(
                        f"列{c}（{pos}）のヘッダー「{v}」は連番の数値です。意味のある列名を設定してください。"
                    ),
                    severity="error",
                )
            )
        return violations

    @staticmethod
    def _merge_overlaps_header(merged: MergedRange, header_rows: list[int]) -> bool:
        """結合セルがヘッダー行のいずれかに重なるか判定する。"""
        for hr in header_rows:
            if merged.start_row <= hr <= merged.end_row:
                return True
        return False
