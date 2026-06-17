"""Harunobu コアデータモデル"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from harunobu.core.severity import Severity


def safe_validate(model_cls: type, obj: Any) -> Any:
    """Streamlit の再import でクラスIDが変わっても安全に Pydantic モデルを取得する。

    Streamlit はスクリプト再実行ごとにモジュールを再import するため、
    session_state に保存された旧クラスのインスタンスは isinstance チェックに失敗し、
    model_validate もそのまま受け付けない。model_dump() → model_validate() で安全に再構築する。
    """
    if isinstance(obj, model_cls):
        return obj
    if hasattr(obj, "model_dump"):
        return model_cls.model_validate(obj.model_dump())
    return model_cls.model_validate(obj)


# ─── 内部データモデル (WorkBook / Sheet / Cell) ───


class CellPosition(BaseModel):
    """セル位置"""

    row: int
    col: int

    def __str__(self) -> str:
        """A1 形式のセル参照文字列を返す（例: row=1, col=1 → ``A1``）。"""
        col_letter = ""
        c = self.col
        while c > 0:
            c, remainder = divmod(c - 1, 26)
            col_letter = chr(65 + remainder) + col_letter
        return f"{col_letter}{self.row}"


class CellFormat(BaseModel):
    """セル書式情報"""

    bold: bool = False
    italic: bool = False
    font_color: str | None = None
    bg_color: str | None = None
    number_format: str | None = None
    alignment: str | None = None
    border_left: str | None = None
    border_right: str | None = None
    border_top: str | None = None
    border_bottom: str | None = None


class Cell(BaseModel):
    """セルデータ"""

    pos: CellPosition
    value: Any = None
    fmt: CellFormat = Field(default_factory=CellFormat)
    formula: str | None = None
    is_merged: bool = False
    merge_master: CellPosition | None = None


class FormulaRef(BaseModel):
    """OOXML から抽出した数式セル参照"""

    sheet_name: str
    cell_ref: str
    row: int
    col: int
    formula_type: str | None = None
    formula_text: str | None = None


class FormulaErrorRef(BaseModel):
    """OOXML から抽出した数式関連エラーセル参照"""

    sheet_name: str
    cell_ref: str
    row: int
    col: int
    error_text: str


class ObjectRef(BaseModel):
    """OOXML drawing*.xml から抽出したオブジェクト参照。

    row / col は 1-indexed でアンカーの起点セル（xdr:from）を示す。
    """

    sheet_name: str
    object_type: Literal["image", "chart", "shape", "connector"]
    row: int
    col: int
    name: str | None = None
    drawing_part: str


class MergedRange(BaseModel):
    """結合セル範囲"""

    start_row: int
    start_col: int
    end_row: int
    end_col: int

    def __str__(self) -> str:
        """結合範囲を A1 形式の範囲文字列で返す（例: ``A1:C3``）。"""
        start = CellPosition(row=self.start_row, col=self.start_col)
        end = CellPosition(row=self.end_row, col=self.end_col)
        return f"{start}:{end}"


class CsvIssueSample(BaseModel):
    """CSV raw 診断の代表issue"""

    issue_type: str
    logical_row: int
    col: int | None = None
    cell_range: str | None = None
    physical_start_line: int
    physical_end_line: int
    severity: Literal["error", "warning", "info"] = "warning"
    description: str = ""
    raw_preview: str = ""
    value_preview: str = ""
    field_count: int | None = None
    expected_field_count: int | None = None
    was_quoted: bool = False


class CsvDiagnostics(BaseModel):
    """CSV/TSV raw 診断サマリ。

    巨大CSVでもメモリを増やしすぎないよう、全行・全フィールドではなく
    件数と代表sampleだけを保持する。
    """

    delimiter: str
    total_records: int | None = 0
    scanned_records: int = 0
    expected_field_count: int | None = None
    field_count_histogram: dict[int, int] = Field(default_factory=dict)
    issue_counts: dict[str, int] = Field(default_factory=dict)
    issue_samples: list[CsvIssueSample] = Field(default_factory=list)
    truncated: bool = False
    abort_reason: str | None = None
    max_issue_samples: int = 0
    max_issues_before_abort: int = 0
    confidence: float = 1.0


class Sheet(BaseModel):
    """シートデータ"""

    name: str
    cells: dict[tuple[int, int], Cell] = Field(default_factory=dict)
    merged_cells: list[MergedRange] = Field(default_factory=list)
    max_row: int = 0
    max_col: int = 0
    hidden: bool = False
    hidden_rows: list[int] = Field(default_factory=list)
    hidden_cols: list[int] = Field(default_factory=list)
    row_groups: list[tuple[int, int]] = Field(default_factory=list)
    col_groups: list[tuple[int, int]] = Field(default_factory=list)
    csv_diagnostics: CsvDiagnostics | None = None
    formula_refs: list[FormulaRef] = Field(default_factory=list)
    formula_error_refs: list[FormulaErrorRef] = Field(default_factory=list)
    formula_refs_loaded: bool = False
    formula_refs_error: str | None = None
    object_refs: list[ObjectRef] = Field(default_factory=list)
    object_refs_loaded: bool = False
    object_refs_error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    def get_cell(self, row: int, col: int) -> Cell | None:
        """指定座標のセルを返す（存在しなければ ``None``）。"""
        return self.cells.get((row, col))

    def get_cell_value(self, row: int, col: int) -> Any:
        """指定座標のセルの値を返す（存在しなければ ``None``）。"""
        cell = self.cells.get((row, col))
        return cell.value if cell else None

    def iter_cells(self, start_row: int, start_col: int, end_row: int, end_col: int):
        """指定範囲のセルをイテレート"""
        for r in range(start_row, end_row + 1):
            for c in range(start_col, end_col + 1):
                cell = self.cells.get((r, c))
                if cell:
                    yield cell


class WorkBook(BaseModel):
    """ワークブックデータ"""

    file_name: str
    file_format: Literal["xlsx", "csv", "tsv"]
    sheets: list[Sheet] = Field(default_factory=list)
    file_size: int = 0
    file_path: str | None = None
    """元ファイルの絶対パス（ビジュアル分析等で使用、read_file 経由時に設定）"""
    encoding: str | None = None
    """ファイル読み込み時に確定したテキストエンコーディング。

    CSV/TSV では ``utf-8`` / ``utf-8-sig`` / ``cp932`` のいずれか。
    xlsx ではエンコーディング概念がないため ``None``。"""

    def get_sheet(self, name: str) -> Sheet | None:
        """指定名のシートを返す（存在しなければ ``None``）。"""
        for sheet in self.sheets:
            if sheet.name == name:
                return sheet
        return None


# ─── レイアウト推定結果 ───


class CellRange(BaseModel):
    """セル範囲"""

    start_row: int
    start_col: int
    end_row: int
    end_col: int

    def __str__(self) -> str:
        """セル範囲を A1 形式の範囲文字列で返す（例: ``A1:C3``）。"""
        start = CellPosition(row=self.start_row, col=self.start_col)
        end = CellPosition(row=self.end_row, col=self.end_col)
        return f"{start}:{end}"


class ColumnHeader(BaseModel):
    """列ヘッダー情報"""

    col_index: int
    header_rows: list[int] = Field(default_factory=list)
    label: str = ""
    is_merged: bool = False


class ColumnSchema(BaseModel):
    """列スキーマ情報（型推定結果）"""

    col_index: int
    inferred_type: Literal["text", "numeric", "date", "mixed", "empty"] = "mixed"
    has_header: bool = True


class SheetProperty(BaseModel):
    """シートプロパティ"""

    sheet_name: str
    max_row: int = 0
    max_col: int = 0
    hidden: bool = False


class OtherCell(BaseModel):
    """テーブル外セル"""

    row: int
    col: int
    value: Any = None
    region_type: str = "unknown"


class TableLayout(BaseModel):
    """テーブルレイアウト情報"""

    header_rows: list[int] = Field(default_factory=list)
    body_start_row: int = 1
    body_end_row: int = 1
    column_headers: list[ColumnHeader] = Field(default_factory=list)
    columns: list[ColumnSchema] = Field(default_factory=list)
    stub_cols: list[int] = Field(default_factory=list)
    footer_rows: list[int] = Field(default_factory=list)


class TableRegion(BaseModel):
    """検出されたテーブル領域"""

    range: CellRange
    layout: TableLayout = Field(default_factory=TableLayout)
    confidence: float = 0.0
    abstain: bool = False
    column_headers: list[ColumnHeader] = Field(default_factory=list)
    columns: list[ColumnSchema] = Field(default_factory=list)


class DetectionResult(BaseModel):
    """レイアウト検出結果（テーブル + テーブル外セル）"""

    tables: list[TableRegion] = Field(default_factory=list)
    others: list[OtherCell] = Field(default_factory=list)


class Region(BaseModel):
    """非テーブル領域（タイトル行等）"""

    range: CellRange
    region_type: str = "unknown"


# ─── 採点結果 ───

#: violations がこの件数を超えた場合、UI / writers は violation_groups を参照して要約表示する。
VIOLATIONS_DISPLAY_LIMIT: int = 20


class Violation(BaseModel):
    """違反箇所"""

    sheet: str
    cell_range: str
    description: str
    severity: Literal["error", "warning", "info"] = "error"


class ViolationGroup(BaseModel):
    """(sheet, severity) でグループ化した違反集計。

    violations が VIOLATIONS_DISPLAY_LIMIT を超えた場合に
    UI / writers が参照する表示最適化用の集計単位。
    violations 自体は CheckResult に全件保持され、このクラスは参照用。
    """

    sheet: str
    severity: Literal["error", "warning", "info"]
    count: int
    samples: list[Violation] = Field(default_factory=list)
    """代表サンプル（最大 3 件）。説明文の確認用。"""


class CheckResult(BaseModel):
    """採点結果（1ルール分）

    ルール側は OK/NG と違反内容のみを返す。点数はここでは付与しない
    （レベル別スコアは ``harunobu.core.scorer.LevelScorer`` が責務として
    切り離されている）。

    ``severity`` の決定ルール:

    - ルール側が ``check()`` 内で明示的に値を設定した場合はそれを尊重する
      （例: L1-12 がヘッダー結合なら ``MAJOR``、ボディなら ``FATAL`` のように
      条件で切り替える）
    - 未設定（``None``）の場合は ``MRChecker`` がルールクラスの ``severity``
      属性で注入する
    - Scorer などの後段では非 ``None`` を前提とする
    """

    rule_id: str
    passed: bool
    severity: Severity | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    violations: list[Violation] = Field(default_factory=list)
    message: str = ""

    @property
    def effective_severity(self) -> Severity:
        """severity が未設定でも常に値を返す（フォールバック: MAJOR）。

        通常は ``MRChecker`` がルールの ``severity`` 属性を注入するため
        ``None`` にはならないが、テストなどで Analyzer を経由せずに
        ``CheckResult`` を直接生成するケースのためのセーフネット。
        """
        return self.severity if self.severity is not None else Severity.MAJOR

    @property
    def is_skipped(self) -> bool:
        """confidence=0 のルールは採点対象外（判定対象外）。"""
        return self.confidence == 0

    @property
    def is_display_truncated(self) -> bool:
        """violations 件数が表示閾値（VIOLATIONS_DISPLAY_LIMIT）を超えているか。

        True の場合、UI / writers は violation_groups を参照して要約表示を行う。
        violations 自体は全件を保持し続ける（このプロパティは変異しない）。
        """
        return len(self.violations) > VIOLATIONS_DISPLAY_LIMIT

    @property
    def violation_groups(self) -> list[ViolationGroup]:
        """violations を (sheet, severity) でグループ化した集計を返す。

        件数の多い順にソート。各グループに代表サンプル最大 3 件を含む。
        is_display_truncated が False でも呼び出し可能だが、通常は
        is_display_truncated == True のときに UI / writers から参照される。
        """
        from collections import defaultdict

        groups: dict[tuple[str, str], list[Violation]] = defaultdict(list)
        for v in self.violations:
            groups[(v.sheet, v.severity)].append(v)

        return [
            ViolationGroup(
                sheet=sheet,
                severity=severity,  # type: ignore[arg-type]
                count=len(vs),
                samples=vs[:3],
            )
            for (sheet, severity), vs in sorted(groups.items(), key=lambda x: -len(x[1]))
        ]


class MRResult(BaseModel):
    """機械可読性チェック結果"""

    level1: dict[str, CheckResult] = Field(default_factory=dict)
    level2: dict[str, CheckResult] = Field(default_factory=dict)
    level3: dict[str, CheckResult] = Field(default_factory=dict)

    def all_results(self) -> dict[str, CheckResult]:
        """全レベル（L1/L2/L3）のチェック結果を rule_id 単位で1つの辞書にまとめて返す。"""
        return {**self.level1, **self.level2, **self.level3}


class TableResult(BaseModel):
    """テーブル単位の結果"""

    range: CellRange
    layout: TableLayout
    confidence: float
    mr_result: MRResult = Field(default_factory=MRResult)
    suggestions: list[dict[str, Any]] | None = None
    column_headers: list[ColumnHeader] = Field(default_factory=list)
    columns: list[ColumnSchema] = Field(default_factory=list)


class SheetMeta(BaseModel):
    """シートメタ情報"""

    name: str
    used_range: str = ""
    hidden: bool = False


class SheetResult(BaseModel):
    """シート単位の結果"""

    sheet_meta: SheetMeta
    tables: list[TableResult] = Field(default_factory=list)
    non_table_regions: list[Region] = Field(default_factory=list)
    sheet_property: SheetProperty | None = None
    others: list[OtherCell] = Field(default_factory=list)


class FileMeta(BaseModel):
    """ファイルメタ情報"""

    name: str
    size: int = 0
    format: str = ""
    sheet_count: int = 0


class AnalysisResult(BaseModel):
    """採点結果（全体）

    スコア集計は ``AnalysisResult`` 自身では行わず、
    ``harunobu.core.scorer.LevelScorer`` に委譲する。本モデルは生のルール結果
    （シート/テーブル/ルール）を保持する責務に専念する。
    """

    file_meta: FileMeta
    sheets: list[SheetResult] = Field(default_factory=list)


# ─── Config ───

# モード → 評価対象の機械可読性レベル集合のマッピング。
# mode と mr_levels の整合性を保つ単一の真実の源（single source of truth）。
# Config の検証で mr_levels を導出するほか、analyzer.py からも参照される。
_MODE_LEVELS: dict[str, set[int]] = {
    "lite": {1},
    "standard": {1, 2},
    "thorough": {1, 2, 3},
}


class Config(BaseModel):
    """Harunobu設定"""

    mode: Literal["lite", "standard", "thorough"] = "standard"
    confidence_threshold: float = 0.7
    mr_levels: set[int] = Field(default_factory=lambda: {1, 2})
    enable_suggestions: bool = False
    custom_rules: list[str] = Field(default_factory=list)
    strict: bool = False
    """strict モード: True の場合、ルール実行中の例外をキャッチせず再送出する（開発・テスト用）"""

    @model_validator(mode="after")
    def _derive_mr_levels_from_mode(self) -> Config:
        """mr_levels が明示指定されていない場合に mode から導出する。

        mode と mr_levels の不整合（例: ``mode="thorough"`` なのに Level 3 が
        評価されない）を防ぐため、呼び出し側が mr_levels を明示的に渡さなかった
        ときは mode に対応するレベル集合で上書きする。これにより
        ``analyze(path, Config(mode=...))`` と ``Analyzer(mode)`` が同じ
        レベル集合を評価する。mr_levels を明示指定した場合はそれを尊重する。

        Returns:
            Config: 自身（mr_levels を mode から導出済み）
        """
        if "mr_levels" not in self.model_fields_set:
            self.mr_levels = set(_MODE_LEVELS[self.mode])
        return self


# ─── テーブルコンテキスト（ルールに渡すコンテキスト） ───


class TableContext(BaseModel):
    """ルールチェックに渡すコンテキスト"""

    workbook: Any  # WorkBook（Streamlit再importでクラスIDが変わるためAny）
    sheet: Any  # Sheet（同上）
    table_region: TableRegion
    config: Config = Field(default_factory=Config)
    all_tables: list[TableRegion] = Field(default_factory=list)
    """同一シート上の全テーブル領域（LayoutDetector結果のキャッシュ）"""
    sheet_others: list[OtherCell] = Field(default_factory=list)
    """detect_with_others がそのシートについて返したテーブル外セル（L1-04 等）"""

    model_config = {"arbitrary_types_allowed": True}
