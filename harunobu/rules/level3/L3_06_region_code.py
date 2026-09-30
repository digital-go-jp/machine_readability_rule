"""L3-06: 地域コード又は地域名称が表記されているか"""

from __future__ import annotations

import re

from harunobu.core.models import (
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.resources.region_dict import (
    municipality_aliases,
    municipality_codes,
    municipality_names,
    prefecture_codes,
    prefecture_names,
    prefecture_short_names,
)
from harunobu.rules.base import RuleBase, TargetFormat

try:
    from harunobu.core.ai_semantic_checker import AISemanticChecker
except ImportError:
    AISemanticChecker = None  # type: ignore[assignment,misc]


# 辞書はリソース（harunobu/resources/region_dict.json）から動的にロードする。
def _prefectures() -> frozenset[str]:
    return prefecture_names()


def _prefecture_short() -> frozenset[str]:
    return prefecture_short_names()


def _prefecture_codes_set() -> frozenset[str]:
    return prefecture_codes()


def _municipality_names() -> frozenset[str]:
    return municipality_names()


def _municipality_aliases() -> frozenset[str]:
    return municipality_aliases()


def _municipality_codes_set() -> frozenset[str]:
    return municipality_codes()


# 地域に関連するヘッダーキーワード
_REGION_HEADER_KEYWORDS = re.compile(
    r"(都道府県|地域|地区|市区町村|自治体|所在地|住所|県|府|市|町|村|region|prefecture|city|address|地域コード|団体コード)",
    re.IGNORECASE,
)

# 全国地方公共団体コード（6桁）パターン
_LOCAL_GOV_CODE = re.compile(r"^\d{6}$")

# 都道府県コード（2桁）パターン
_PREF_CODE = re.compile(r"^(0[1-9]|[1-3]\d|4[0-7])$")


class RegionCodeRule(RuleBase):
    """地域コードまたは地域名称が標準的に表記されているかを検査する。

    地域データに標準地域コード（JIS X 0401/0402）または正式な地域名称が用いられているかを確認し、
    非標準な省略表記を違反として検出する。
    """

    rule_id = "L3-06"
    rule_name = "地域コード又は正式な地域名称が表記されているか"
    level = 3
    target = TargetFormat.COMMON
    description = "地域データには標準地域コード（JIS X 0401/0402）または正式な地域名称が使用されているか確認します。"

    severity = Severity.CRITICAL

    def check(self, context: TableContext) -> CheckResult:
        """地域コードまたは地域名称が標準的に表記されているかを検査する。"""
        violations: list[Violation] = []
        sheet = context.sheet
        table = context.table_region
        layout = table.layout

        if not layout.header_rows:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.5,
                violations=[],
                message="ヘッダー行が検出されなかったためスキップ",
            )

        header_row = layout.header_rows[-1]
        start_col = table.range.start_col
        end_col = table.range.end_col
        body_start = layout.body_start_row
        body_end = layout.body_end_row

        prefectures = _prefectures()
        prefecture_shorts = _prefecture_short()
        muni_names = _municipality_names()
        muni_aliases = _municipality_aliases()

        # 地域列の検出
        region_columns: list[tuple[int, str]] = []
        for col in range(start_col, end_col + 1):
            cell = sheet.get_cell(header_row, col)
            if cell and cell.value:
                header = str(cell.value).strip()
                if _REGION_HEADER_KEYWORDS.search(header):
                    region_columns.append((col, header))

        if not region_columns:
            # 地域列がなければデータ内容から推定
            for col in range(start_col, end_col + 1):
                if _column_contains_regions(sheet, col, layout):
                    cell = sheet.get_cell(header_row, col)
                    header = str(cell.value).strip() if cell and cell.value else f"列{col}"
                    region_columns.append((col, header))

        if not region_columns:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.6,
                violations=[],
                message="地域データ列が検出されませんでした",
            )

        # 地域列の標準化チェック
        for col, header in region_columns:
            has_code_column = any("コード" in h or "code" in h.lower() for _, h in region_columns)

            for row in range(body_start, body_end + 1):
                cell = sheet.get_cell(row, col)
                if cell is None or cell.value is None:
                    continue

                val = str(cell.value).strip()
                if not val:
                    continue

                # 都道府県の省略形チェック（「県」なし等）
                # 「北海道」「東京都」など正式名称が「短縮形」と一致するケースは除外
                if val in prefecture_shorts and val not in prefectures:
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description=(f"都道府県名が省略されています: '{val}' → 正式名称を使用してください"),
                            severity="warning",
                        )
                    )
                    continue

                # 市区町村の省略形チェック（「市」「区」抜きなど）
                # 正式名称（"札幌市" 等）と重複しない場合に省略形と判定
                if val in muni_aliases and val not in muni_names:
                    violations.append(
                        Violation(
                            sheet=sheet.name,
                            cell_range=str(cell.pos),
                            description=(f"市区町村名が省略されています: '{val}' → 正式名称を使用してください"),
                            severity="warning",
                        )
                    )
                    continue

                # 地域名があるがコード列がない場合
                if (val in prefectures or val in muni_names) and not has_code_column:
                    # 最初の1回だけ報告
                    if not any("地域コード列" in v.description for v in violations):
                        violations.append(
                            Violation(
                                sheet=sheet.name,
                                cell_range=str(cell.pos),
                                description=("地域コード列が見つかりません。標準地域コードの列を追加してください"),
                                severity="info",
                            )
                        )

        # AIセマンティックチェック: ヘッダーの明確さを評価
        ai_available = False
        if AISemanticChecker is not None:
            ai_checker = AISemanticChecker.get_instance()
            if ai_checker.is_available():
                ai_available = True
                # 全ヘッダーを収集して明確さを評価
                all_headers: list[str] = []
                for col in range(start_col, end_col + 1):
                    cell = sheet.get_cell(header_row, col)
                    if cell and cell.value:
                        all_headers.append(str(cell.value).strip())

                if all_headers:
                    ambiguous_results = ai_checker.assess_column_header_clarity(all_headers)
                    for item in ambiguous_results:
                        header_name = item.get("header", "")
                        reason = item.get("reason", "")
                        suggested = item.get("suggested_improvement", "")
                        # 地域関連のヘッダーのみ報告（曖昧なヘッダーで地域データが隠れている可能性）
                        if item.get("is_ambiguous", False) and header_name:
                            # 既に報告済みのヘッダーは除外
                            already_reported = any(header_name in v.description for v in violations)
                            if not already_reported:
                                violations.append(
                                    Violation(
                                        sheet=sheet.name,
                                        cell_range=f"R{header_row}",
                                        description=(
                                            f"ヘッダー '{header_name}' が曖昧です（AI検出）: "
                                            f"{reason}。改善案: {suggested}"
                                        ),
                                        severity="info",
                                    )
                                )

        passed = len(violations) == 0

        # AI利用時は信頼度を上げる
        confidence = 0.80 if ai_available else 0.70

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=confidence,
            violations=violations,
            message=(
                f"地域コード/名称の問題: {len(violations)}件検出"
                if violations
                else "地域コード/名称は適切に表記されています"
            ),
        )


def _column_contains_regions(sheet, col: int, layout) -> bool:
    """列が地域データ（都道府県/市区町村）を含むか推定する。"""
    body_start = layout.body_start_row
    body_end = layout.body_end_row

    prefectures = _prefectures()
    prefecture_shorts = _prefecture_short()
    muni_names = _municipality_names()
    muni_aliases = _municipality_aliases()

    region_count = 0
    total = 0

    for row in range(body_start, min(body_end + 1, body_start + 30)):
        cell = sheet.get_cell(row, col)
        if cell and cell.value:
            val = str(cell.value).strip()
            total += 1
            if val in prefectures or val in prefecture_shorts or val in muni_names or val in muni_aliases:
                region_count += 1

    if total == 0:
        return False
    return region_count / total >= 0.5
