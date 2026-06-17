"""L1-06: 体裁用スペース・改行チェック"""

from __future__ import annotations

import re

from harunobu.core.models import (
    CellPosition,
    CheckResult,
    TableContext,
    Violation,
)
from harunobu.core.severity import Severity
from harunobu.rules.base import RuleBase, TargetFormat


class WhitespaceFormattingRule(RuleBase):
    """体裁目的のスペースや改行が含まれていないことを確認する。"""

    rule_id = "L1-06"
    rule_name = "スペースや改行等で体裁を整えていないか"
    level = 1
    target = TargetFormat.COMMON
    description = (
        "セル内に体裁目的のスペース（先頭・末尾の空白、全角スペース、連続スペース）"
        "や不要な改行が含まれていないことを確認します。"
    )

    severity = Severity.CRITICAL
    # 体裁用スペースのパターン
    _LEADING_TRAILING_RE = re.compile(r"^\s+|\s+$")
    _CONSECUTIVE_SPACES_RE = re.compile(r"[ \u3000]{2,}")
    _FULLWIDTH_SPACE_RE = re.compile(r"\u3000")

    # 住所系カラムを判定するパターン（全角スペースが意図的に使われる）
    _ADDRESS_HEADER_RE = re.compile(
        r"(住所|所在地|address|addr|勤務地|居所|連絡先住所|本籍|現住所|送付先)",
        re.IGNORECASE,
    )

    # セマンティックな全角スペース使用パターン（FP除外用）
    # 日本語リストマーカー（ア〜ン、ａ〜ｚ）+ 全角スペース
    _LIST_MARKER_RE = re.compile(r"^[ア-ンa-zａ-ｚ①-⑳（\(][）\)]?\u3000")
    # 注釈マーカー（※、注）+ 全角スペース
    _NOTE_MARKER_RE = re.compile(r"^※\d*\u3000")
    # タイトル・見出しパターン（第X表、第X章等）
    _TITLE_RE = re.compile(r"^第[０-９0-9一二三四五六七八九十]+\u3000")
    # 〃（同上）の前にインデント用スペース
    _DITTO_INDENT_RE = re.compile(r"^\u3000+〃$")
    # インデント + ○/●/・マーカー（箇条書きパターン）
    _BULLET_INDENT_RE = re.compile(r"^\u3000+[○●・◯]\u3000?")
    # セクション番号パターン（[概況] 1.xxx、Ⅰ．xxx 等）
    _SECTION_RE = re.compile(
        r"^(\[.+?\])\u3000?[0-9０-９]"
        r"|^[\u2160-\u217F][．.]\u3000?"
        r"|^[0-9０-９]+[．.]\u3000"
    )
    # 段落インデント（先頭3つ以上の全角スペース + 文章）
    _PARAGRAPH_INDENT_RE = re.compile(r"^\u3000{2,}[0-9０-９]+[．.]")
    # 単位表記パターン（(B)/(A)　(%)等）
    _UNIT_EXPR_RE = re.compile(r"\([A-Za-z]\)/\([A-Za-z]\)\u3000")

    # 内部改行を違反とみなすときの空白密度下限（これを超えたら体裁目的の改行とみなす）
    _INTERNAL_NEWLINE_DENSITY_MAX = 0.10

    @staticmethod
    def _whitespace_char_count(value: str) -> int:
        return sum(1 for c in value if c.isspace())

    @classmethod
    def _whitespace_density_ratio(cls, value: str) -> float:
        return cls._whitespace_char_count(value) / max(len(value), 1)

    @staticmethod
    def _has_internal_line_break(value: str) -> bool:
        r"""末尾の \r\n のみの改行は除き、セル途中に改行があるかを判定する。"""
        content = value.rstrip("\r\n")
        return "\n" in content or "\r" in content

    def _get_address_columns(self, context: TableContext) -> set[int]:
        """住所系のカラムインデックスを返す。"""
        address_cols: set[int] = set()
        layout = context.table_region.layout
        sheet = context.sheet
        region = context.table_region.range

        header_rows = layout.header_rows if layout.header_rows else [region.start_row]
        for hr in header_rows:
            for c in range(region.start_col, region.end_col + 1):
                cell = sheet.get_cell(hr, c)
                if cell and cell.value is not None:
                    header_val = str(cell.value)
                    if self._ADDRESS_HEADER_RE.search(header_val):
                        address_cols.add(c)
        return address_cols

    def _is_semantic_fullwidth_space(self, value: str) -> bool:
        """全角スペースがセマンティック（意味的）に使われているかを判定する。

        行政データでは以下のパターンで全角スペースが意図的に使用される:
        - リストマーカー（ア、イ、ウ...）の後の区切り
        - 注釈（※1、※2...）の後の区切り
        - タイトル（第5表 等）の後の区切り
        - 同上記号（〃）のインデント
        """
        return bool(
            self._LIST_MARKER_RE.match(value)
            or self._NOTE_MARKER_RE.match(value)
            or self._TITLE_RE.match(value)
            or self._DITTO_INDENT_RE.match(value)
            or self._BULLET_INDENT_RE.match(value)
            or self._SECTION_RE.match(value)
            or self._PARAGRAPH_INDENT_RE.match(value)
            or self._UNIT_EXPR_RE.search(value)
        )

    def _check_cell_value(self, value: str, *, is_address_col: bool = False) -> list[str]:
        """セル値に含まれる体裁用スペース・改行の問題を検出する。

        Args:
            value (str): セル値
            is_address_col (bool): 住所系カラムの場合 True（全角スペースを許容）
        """
        issues: list[str] = []

        # 先頭・末尾の空白（改行含む）を検出
        # ただし、セル内改行(\n)が末尾にある場合はExcelの表示上の都合なので除外
        # また、セマンティックな先頭全角スペース（リストマーカー等）は除外
        stripped = value.strip()
        check_val = value.rstrip("\n")  # 末尾改行のみ除外して判定
        if check_val != check_val.strip():
            # セマンティックな全角スペースパターンは除外
            if not self._is_semantic_fullwidth_space(value):
                issues.append("先頭または末尾に空白があります")

        # 全角スペース検出（住所系カラム、セマンティック使用は除外）
        if not is_address_col and self._FULLWIDTH_SPACE_RE.search(value):
            if not self._is_semantic_fullwidth_space(value):
                issues.append("全角スペースが含まれています")

        # 連続スペース検出（住所系カラムは除外、セマンティック使用も除外）
        if not is_address_col and self._CONSECUTIVE_SPACES_RE.search(stripped):
            if not self._is_semantic_fullwidth_space(value):
                issues.append("連続するスペースが含まれています")

        # セル途中の改行（長文で改行が疎な場合は密度が下がるため許容）
        if self._has_internal_line_break(value):
            if self._whitespace_density_ratio(value) > self._INTERNAL_NEWLINE_DENSITY_MAX:
                issues.append("セル内に体裁目的の改行が含まれています")

        return issues

    def check(self, context: TableContext) -> CheckResult:
        """体裁目的のスペース（前後の空白・全角・連続）や改行の有無を検査する。"""
        sheet = context.sheet
        region = context.table_region.range
        violations: list[Violation] = []
        address_cols = self._get_address_columns(context)

        for cell in sheet.iter_cells(region.start_row, region.start_col, region.end_row, region.end_col):
            if cell.value is None:
                continue
            val = str(cell.value)
            if not val:
                continue

            is_address_col = cell.pos.col in address_cols
            issues = self._check_cell_value(val, is_address_col=is_address_col)
            if issues:
                pos = CellPosition(row=cell.pos.row, col=cell.pos.col)
                violations.append(
                    Violation(
                        sheet=sheet.name,
                        cell_range=str(pos),
                        description=f"{pos}: {'; '.join(issues)}（値: '{val[:30]}'）",
                        severity="warning",
                    )
                )

        if not violations:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                confidence=0.95,
                message="体裁用スペース・改行は検出されませんでした。",
            )

        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            confidence=0.95,
            violations=violations,
            message=f"{len(violations)}件の体裁用スペース・改行が検出されました。",
        )
