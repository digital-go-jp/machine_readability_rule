"""L1-08: 機種依存文字チェック"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from harunobu.core.models import (
    CellPosition,
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat

_CSV_PATH = Path(__file__).parent / "L1_08_platform_dependent_chars.csv"

# 単位記号（広く使われるため info、かつ単独セルでは報告しない）
_UNIT_SYMBOLS = frozenset("㎡㎥㎢㎠㎝㎞㎜㎏㎎㎍㎅㎄㎃㎖㎗㎘㏄㏊")


def _load_special_chars() -> dict[str, tuple[str, str]]:
    """Unicode 範囲指定でカバーできない特殊文字を CSV から読み込む。

    波ダッシュ・全角チルダ・令和合字や Mac 固有文字等、範囲指定では
    分類しきれない（または `_classify_range()` のデフォルトと異なる
    カテゴリを付けたい）文字をここで管理する。
    """
    chars: dict[str, tuple[str, str]] = {}
    if not _CSV_PATH.exists():
        return chars
    with _CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ch = row["char"]
            if not ch:
                continue
            chars[ch] = (row["category"], row["severity"])
    return chars


_SPECIAL_CHARS: dict[str, tuple[str, str]] = _load_special_chars()

# 行政データの分類コード（Ⅰ-0, Ⅱ－１ 等）— ローマ数字を分類コードとして使用しているケースは info に降格
_ROMAN_CODE_RE = re.compile(r"^[Ⅰ-ⅿ][ー－\-][０-９0-9]+$")

_CATEGORY_LABELS = {
    "circled_number": "丸数字",
    "roman_numeral": "ローマ数字",
    "platform_symbol": "機種依存記号",
    "unit_symbol": "単位記号",
    "fullwidth_alnum": "全角英数字",
    "wave_dash": "波ダッシュ",
    "fullwidth_tilde": "全角チルダ",
    "reiwa_era": "令和合字",
}


def _classify_range(ch: str) -> tuple[str, str] | None:
    """Unicode コードポイント範囲ベースで (category, severity) を返す。

    検出対象外なら None。範囲は CP932 拡張領域 (JIS X 0208 にない記号)
    のうち実用的に問題となりやすいものを列挙している。
    """
    cp = ord(ch)
    # 丸数字 U+2460-2473 (①-⑳), U+3251-325F (㉑-㉟), U+32B1-32BF (㊱-㊿)
    if 0x2460 <= cp <= 0x2473 or 0x3251 <= cp <= 0x325F or 0x32B1 <= cp <= 0x32BF:
        return ("circled_number", "warning")
    # ローマ数字 U+2160-217F (Ⅰ-ⅿ)
    if 0x2160 <= cp <= 0x217F:
        return ("roman_numeral", "warning")
    # 全角英数字 U+FF10-FF19 (０-９), U+FF21-FF3A (Ａ-Ｚ), U+FF41-FF5A (ａ-ｚ)
    if 0xFF10 <= cp <= 0xFF19 or 0xFF21 <= cp <= 0xFF3A or 0xFF41 <= cp <= 0xFF5A:
        return ("fullwidth_alnum", "info")
    # 単位記号（U+3300-33FF の一部）
    if ch in _UNIT_SYMBOLS:
        return ("unit_symbol", "info")
    # 機種依存記号: 括弧囲み・CJK互換単位・CJK互換形式
    if (
        0x3220 <= cp <= 0x3243
        or 0x3280 <= cp <= 0x32FE  # U+32FF (㋿) は _SPECIAL_CHARS で個別扱い
        or 0x3300 <= cp <= 0x33FF
        or 0xFE30 <= cp <= 0xFE4F
    ):
        return ("platform_symbol", "warning")
    return None


def _classify(ch: str) -> tuple[str, str] | None:
    """文字から (category, severity) を返す。検出対象外なら None。

    優先順位: CSV の特殊文字（範囲ベースを上書き） > Unicode 範囲ベース判定。
    """
    if ch in _SPECIAL_CHARS:
        return _SPECIAL_CHARS[ch]
    return _classify_range(ch)


class PlatformDependentCharsRule(RuleBase):
    """機種依存文字が含まれていないことを確認する。

    検出対象は Unicode コードポイント範囲ベースで判定する（``_classify_range``）。
    範囲指定でカバーできない特殊文字（㋿、波ダッシュ〜、全角チルダ～、Mac 固有文字等）は
    同階層の ``L1_08_platform_dependent_chars.csv`` で補完する。将来 Mac 固有文字や
    新たな警告対象を追加する場合は CSV へ 1 行追記すれば足りる。

    挙動はファイル読み込み時のエンコーディングで分岐する:

    - Shift-JIS（CP932）として読み込まれた場合 — 機種依存文字検出時に
      ``passed=False`` とする。
    - UTF-8 / xlsx の場合 — Unicode コードポイントが一意のため真の互換性
      リスクは低いが、同じ検出結果を warning として参考報告する
      （``passed=True``）。
    """

    rule_id = "L1-08"
    rule_name = "機種依存文字を使用していないか"
    level = 1
    target = TargetFormat.COMMON
    description = (
        "セル内に機種依存文字（丸数字、ローマ数字、特殊記号等）が含まれていないことを確認します。"
        "全角英数字は軽微な指摘として報告します。"
        "Shift-JIS で読み込んだ場合のみ NG 判定とし、UTF-8 / xlsx は warning として参考報告します。"
    )

    severity = Severity.CRITICAL

    def _detect_in_cell(self, value: str) -> list[tuple[str, str]]:
        """セル文字列から検出された (issue_description, severity) を返す。

        - 同一カテゴリの文字は最大5文字まで例示
        - ローマ数字の分類コード（Ⅰ-0 等）は info に降格
        - 単位記号（㎡ 等の広く使われる文字）のみのケースは報告しない
        """
        by_category: dict[str, list[str]] = {}
        for ch in value:
            entry = _classify(ch)
            if entry is None:
                continue
            category, _ = entry
            by_category.setdefault(category, []).append(ch)

        if not by_category:
            return []

        is_roman_code = bool(_ROMAN_CODE_RE.match(value.strip()))

        issues: list[tuple[str, str]] = []
        for category, chars in by_category.items():
            severity = _classify(chars[0])[1]  # type: ignore[index]
            if category == "unit_symbol":
                # 広く使われる単位記号のみなら報告しない
                continue
            if category == "roman_numeral" and is_roman_code:
                severity = "info"
            label = _CATEGORY_LABELS.get(category, category)
            sample = "".join(chars[:5])
            if category == "roman_numeral" and is_roman_code:
                issues.append((f"{label}（分類コード）: {sample}", severity))
            else:
                issues.append((f"{label}: {sample}", severity))
        return issues

    def check(self, context: TableContext) -> CheckResult:
        """機種依存文字（丸数字・ローマ数字・特殊記号等）の有無を検査する。"""
        sheet = context.sheet
        region = context.table_region.range
        is_sjis = context.workbook.encoding == "cp932"

        violations: list[Violation] = []
        warning_cells = 0  # severity=warning のセル数（真の機種依存文字）
        info_cells = 0  # severity=info のセル数（全角英数字、分類コード等）

        for cell in sheet.iter_cells(region.start_row, region.start_col, region.end_row, region.end_col):
            if cell.value is None:
                continue
            val = str(cell.value)
            if not val:
                continue

            issues = self._detect_in_cell(val)
            if not issues:
                continue

            has_warning = any(sev == "warning" for _, sev in issues)
            has_info = any(sev == "info" for _, sev in issues)

            if has_warning:
                warning_cells += 1
            elif has_info:
                info_cells += 1

            pos = CellPosition(row=cell.pos.row, col=cell.pos.col)
            cell_severity = "warning" if has_warning else "info"
            descriptions = [desc for desc, _ in issues]
            violations.append(
                Violation(
                    sheet=sheet.name,
                    cell_range=str(pos),
                    description=f"{pos}: {'; '.join(descriptions)}",
                    severity=cell_severity,
                )
            )

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.95,
                message="機種依存文字は検出されませんでした。",
            )

        if is_sjis:
            # CP932 として読み込まれた場合のみ NG 判定とする。
            passed = warning_cells == 0

            if warning_cells > 0:
                message = f"{warning_cells}件のセルで機種依存文字が検出されました。"
                if info_cells > 0:
                    message += f" また、{info_cells}件のセルで全角英数字が検出されました。"
            else:
                message = (
                    f"{info_cells}件のセルで全角英数字が検出されました"
                    f"（機種依存文字ではありませんが、半角の使用を推奨します）。"
                )
        else:
            # UTF-8 / xlsx では Unicode コードポイントが一意のため真の互換性リスクは低い。
            # 検出結果は warning として参考報告するが passed=True。
            passed = True
            total = warning_cells + info_cells
            message = (
                f"{total}件のセルで機種依存文字または全角英数字が検出されました"
                f"（UTF-8 / xlsx のため互換性リスクは低く warning として参考報告します）。"
            )

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            confidence=0.95,
            violations=violations,
            message=message,
        )
