"""出力フォーマットバリデーションテスト

JSON/CSV出力の構造・内容の正確性を包括的に検証する。
"""

from __future__ import annotations

import csv
import io
import json

from harunobu.core.models import (
    AnalysisResult,
    CellRange,
    CheckResult,
    FileMeta,
    MRResult,
    SheetMeta,
    SheetResult,
    TableLayout,
    TableResult,
    Violation,
)
from harunobu.output import csv_writer, json_writer

# ─── テストデータヘルパー ───


def _violation(
    *,
    sheet: str = "Sheet1",
    cell_range: str = "B2",
    description: str = "違反の説明",
    severity: str = "error",
) -> Violation:
    return Violation(
        sheet=sheet,
        cell_range=cell_range,
        description=description,
        severity=severity,
    )


def _check(
    *,
    rule_id: str = "L1-01",
    passed: bool = True,
    confidence: float = 1.0,
    violations: list[Violation] | None = None,
    message: str = "",
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=passed,
        confidence=confidence,
        violations=violations or [],
        message=message,
    )


def _analysis(
    *,
    file_name: str = "test.xlsx",
    file_size: int = 2048,
    file_format: str = "xlsx",
    sheet_count: int = 1,
    sheet_name: str = "Sheet1",
    level1: dict[str, CheckResult] | None = None,
    level2: dict[str, CheckResult] | None = None,
    level3: dict[str, CheckResult] | None = None,
) -> AnalysisResult:
    mr = MRResult(
        level1=level1 or {},
        level2=level2 or {},
        level3=level3 or {},
    )
    return AnalysisResult(
        file_meta=FileMeta(
            name=file_name,
            size=file_size,
            format=file_format,
            sheet_count=sheet_count,
        ),
        sheets=[
            SheetResult(
                sheet_meta=SheetMeta(name=sheet_name, used_range="A1:E10"),
                tables=[
                    TableResult(
                        range=CellRange(start_row=1, start_col=1, end_row=10, end_col=5),
                        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=10),
                        confidence=0.95,
                        mr_result=mr,
                    ),
                ],
            ),
        ],
    )


def _multi_sheet_analysis() -> AnalysisResult:
    """複数シート・複数テーブルのAnalysisResult。"""
    return AnalysisResult(
        file_meta=FileMeta(name="multi.xlsx", size=4096, format="xlsx", sheet_count=2),
        sheets=[
            SheetResult(
                sheet_meta=SheetMeta(name="売上", used_range="A1:D20"),
                tables=[
                    TableResult(
                        range=CellRange(start_row=1, start_col=1, end_row=20, end_col=4),
                        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=20),
                        confidence=0.9,
                        mr_result=MRResult(
                            level1={
                                "L1-12": _check(
                                    rule_id="L1-12",
                                    passed=False,
                                    confidence=0.95,
                                    violations=[
                                        _violation(sheet="売上", cell_range="A1:C1"),
                                        _violation(sheet="売上", cell_range="A5:C5"),
                                    ],
                                    message="結合セルが検出されました",
                                ),
                            },
                            level2={
                                "L2-01": _check(
                                    rule_id="L2-01",
                                    passed=True,
                                    confidence=1.0,
                                    message="数値列は適切です",
                                ),
                            },
                        ),
                    ),
                ],
            ),
            SheetResult(
                sheet_meta=SheetMeta(name="経費", used_range="A1:F15", hidden=True),
                tables=[
                    TableResult(
                        range=CellRange(start_row=1, start_col=1, end_row=15, end_col=6),
                        layout=TableLayout(header_rows=[1], body_start_row=2, body_end_row=15),
                        confidence=0.85,
                        mr_result=MRResult(
                            level1={
                                "L1-06": _check(
                                    rule_id="L1-06",
                                    passed=False,
                                    confidence=0.8,
                                    violations=[
                                        _violation(
                                            sheet="経費",
                                            cell_range="D3",
                                            description="全角スペースが含まれています",
                                            severity="warning",
                                        ),
                                    ],
                                    message="空白文字の書式に問題があります",
                                ),
                            },
                        ),
                    ),
                ],
            ),
        ],
    )


# ─── JSON出力フォーマットバリデーション ───


class TestJsonFormatValidation:
    """JSON出力の構造と内容の正確性を検証する。"""

    def test_top_level_keys_complete(self):
        """トップレベルに全必須キーが含まれる"""
        result = _analysis(file_name="data.xlsx", file_size=3000, file_format="xlsx")
        d = json_writer.to_dict(result)

        required_keys = {"inputファイル名", "ファイルサイズ", "フォーマット", "Sheet数", "レベル別スコア", "sheets"}
        assert required_keys == set(d.keys())

    def test_file_meta_values(self):
        """ファイルメタ情報の値が正しい"""
        result = _analysis(file_name="報告書.xlsx", file_size=5120, file_format="xlsx", sheet_count=3)
        d = json_writer.to_dict(result)

        assert d["inputファイル名"] == "報告書.xlsx"
        assert d["ファイルサイズ"] == 5120
        assert d["フォーマット"] == "xlsx"
        assert d["Sheet数"] == 3

    def test_sheet_level_keys(self):
        """シートレベルに全必須キーが含まれる"""
        result = _analysis()
        d = json_writer.to_dict(result)

        sheet = d["sheets"][0]
        required_keys = {"シート名", "使用範囲", "非表示", "評価対象エリア"}
        assert required_keys == set(sheet.keys())

    def test_hidden_sheet_flag(self):
        """非表示シートのフラグが正しい"""
        result = _multi_sheet_analysis()
        d = json_writer.to_dict(result)

        assert d["sheets"][0]["非表示"] is False
        assert d["sheets"][1]["非表示"] is True

    def test_table_level_keys(self):
        """テーブルレベルに全必須キーが含まれる"""
        result = _analysis(level1={"L1-01": _check()})
        d = json_writer.to_dict(result)

        table = d["sheets"][0]["評価対象エリア"][0]
        required_keys = {"範囲", "信頼度", "ヘッダー行", "ヘッダー範囲", "列数", "評価内容"}
        assert required_keys == set(table.keys())

    def test_table_header_range_derived(self):
        """ヘッダー範囲がヘッダー行とテーブル範囲から導出される"""
        result = _analysis(level1={"L1-01": _check()})
        d = json_writer.to_dict(result)

        table = d["sheets"][0]["評価対象エリア"][0]
        # テーブル範囲 A1:E10 / ヘッダー行 [1] → A1:E1
        assert table["ヘッダー範囲"] == "A1:E1"
        assert table["列数"] == 5

    def test_table_header_range_none_when_no_header(self):
        """ヘッダー行が空のときヘッダー範囲は null"""
        # ヘッダー行なしのテーブルを直接構築
        result = AnalysisResult(
            file_meta=FileMeta(name="x.xlsx", sheet_count=1),
            sheets=[
                SheetResult(
                    sheet_meta=SheetMeta(name="S", used_range="A1:C5"),
                    tables=[
                        TableResult(
                            range=CellRange(start_row=1, start_col=1, end_row=5, end_col=3),
                            layout=TableLayout(header_rows=[], body_start_row=1, body_end_row=5),
                            confidence=0.5,
                            mr_result=MRResult(),
                        )
                    ],
                )
            ],
        )
        d = json_writer.to_dict(result)
        table = d["sheets"][0]["評価対象エリア"][0]
        assert table["ヘッダー範囲"] is None
        assert table["列数"] == 3

    def test_check_result_keys_always_present(self):
        """チェック結果に全キーが常に存在する（メッセージ空文字でも）"""
        result = _analysis(level1={"L1-01": _check(message="")})
        d = json_writer.to_dict(result)

        check = d["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        required_keys = {
            "ルールID",
            "ルール名",
            "ルール説明",
            "合否",
            "判定対象外",
            "重大度",
            "信頼度",
            "違反",
            "メッセージ",
        }
        assert required_keys == set(check.keys())

    def test_check_result_original_description_only_when_opted_in(self):
        """original_description は include_original_description=True の時だけ出力される"""
        result = _analysis(level1={"L1-01": _check(message="")})

        d_default = json_writer.to_dict(result)
        check_default = d_default["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        assert "原本説明" not in check_default

        d_opt_in = json_writer.to_dict(result, include_original_description=True)
        check_opt_in = d_opt_in["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        assert "原本説明" in check_opt_in
        assert check_opt_in["原本説明"]

    def test_message_always_included_even_if_empty(self):
        """メッセージが空文字でもキーが出力される"""
        result = _analysis(level1={"L1-01": _check(message="")})
        d = json_writer.to_dict(result)

        check = d["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        assert "メッセージ" in check
        assert check["メッセージ"] == ""

    def test_message_included_when_nonempty(self):
        """メッセージが非空の場合も正しく出力される"""
        result = _analysis(level1={"L1-01": _check(message="チェック完了")})
        d = json_writer.to_dict(result)

        check = d["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        assert check["メッセージ"] == "チェック完了"

    def test_violations_array_empty_when_passed(self):
        """合格ルールの違反配列が空リスト"""
        result = _analysis(level1={"L1-01": _check(passed=True, violations=[])})
        d = json_writer.to_dict(result)

        check = d["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        assert check["違反"] == []

    def test_violation_fields_complete(self):
        """違反情報に全フィールドが含まれる"""
        v = _violation(sheet="Sheet1", cell_range="A1:C1", description="テスト違反", severity="error")
        result = _analysis(level1={"L1-12": _check(passed=False, violations=[v])})
        d = json_writer.to_dict(result)

        violation = d["sheets"][0]["評価対象エリア"][0]["評価内容"][0]["違反"][0]
        assert set(violation.keys()) == {"シート", "セル範囲", "説明", "違反重大度"}
        assert violation["シート"] == "Sheet1"
        assert violation["セル範囲"] == "A1:C1"
        assert violation["説明"] == "テスト違反"
        assert violation["違反重大度"] == "error"

    def test_multiple_violations_preserved(self):
        """複数違反が全て保持される"""
        violations = [
            _violation(cell_range="A1"),
            _violation(cell_range="B2"),
            _violation(cell_range="C3"),
        ]
        result = _analysis(level1={"L1-12": _check(passed=False, violations=violations)})
        d = json_writer.to_dict(result)

        check = d["sheets"][0]["評価対象エリア"][0]["評価内容"][0]
        assert len(check["違反"]) == 3

    def test_level_score_in_json(self):
        """レベル別スコアが固定減点方式で算出される"""
        result = _analysis(
            level1={"L1-01": _check(passed=True)},
            level2={"L2-01": _check(passed=False)},
        )
        d = json_writer.to_dict(result)

        # L1 全合格 → 100。L2 失敗ルールが MAJOR（デフォルト）→
        # 強制0点ポリシーは FATAL のみ。MAJOR@Level2 の固定減点 30点 → 100-30=70。
        assert d["レベル別スコア"]["1"]["スコア"] == 100
        assert d["レベル別スコア"]["2"]["スコア"] == 70
        assert d["レベル別スコア"]["2"]["強制0点"] is False
        # L3 はルールなし → null
        assert d["レベル別スコア"]["3"] is None

    def test_json_roundtrip(self):
        """JSON文字列が正しくラウンドトリップできる"""
        result = _multi_sheet_analysis()
        json_str = json_writer.to_json(result)
        parsed = json.loads(json_str)

        # 再シリアライズしても同じ
        json_str2 = json.dumps(parsed, ensure_ascii=False, indent=2)
        assert json.loads(json_str) == json.loads(json_str2)

    def test_json_no_ascii_escape(self):
        """JSON文字列で日本語がエスケープされない"""
        result = _analysis(file_name="日本語ファイル.xlsx")
        json_str = json_writer.to_json(result)

        assert "日本語ファイル.xlsx" in json_str
        assert "\\u" not in json_str

    def test_multi_sheet_json_structure(self):
        """複数シートのJSON構造が正しい"""
        result = _multi_sheet_analysis()
        d = json_writer.to_dict(result)

        assert len(d["sheets"]) == 2
        assert d["sheets"][0]["シート名"] == "売上"
        assert d["sheets"][1]["シート名"] == "経費"

    def test_multi_level_rules_in_json(self):
        """複数レベルのルールがJSON内に正しく格納される"""
        result = _analysis(
            level1={"L1-01": _check(rule_id="L1-01")},
            level2={"L2-01": _check(rule_id="L2-01")},
            level3={"L3-01": _check(rule_id="L3-01")},
        )
        d = json_writer.to_dict(result)

        evaluations = d["sheets"][0]["評価対象エリア"][0]["評価内容"]
        rule_ids = {e["ルールID"] for e in evaluations}
        assert rule_ids == {"L1-01", "L2-01", "L3-01"}


# ─── CSV出力フォーマットバリデーション ───


class TestCsvFormatValidation:
    """CSV出力の構造と内容の正確性を検証する。"""

    def test_header_columns_complete(self):
        """ヘッダーに全カラムが含まれる"""
        expected = [
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
        assert csv_writer.HEADER == expected

    def test_header_and_row_original_description_only_when_opted_in(self):
        """原本説明列は include_original_description=True の時だけヘッダー・行に追加される"""
        result = _analysis(level1={"L1-01": _check(message="")})

        rows_default = csv_writer.to_rows(result)
        assert "原本説明" not in rows_default[0]

        rows_opt_in = csv_writer.to_rows(result, include_original_description=True)
        header_opt_in = rows_opt_in[0]
        assert "原本説明" in header_opt_in
        idx = header_opt_in.index("原本説明")
        assert header_opt_in[idx - 1] == "ルール説明"
        assert rows_opt_in[1][idx]

    def test_csv_table_metadata_columns(self):
        """CSVにヘッダー範囲・列数が含まれる"""
        result = _analysis(level1={"L1-01": _check()})
        rows = csv_writer.to_rows(result)

        header = csv_writer.HEADER
        hr_idx = header.index("ヘッダー範囲")
        cc_idx = header.index("列数")
        assert rows[1][hr_idx] == "A1:E1"
        assert rows[1][cc_idx] == "5"

    def test_csv_row_column_count_matches_header(self):
        """データ行のカラム数がヘッダーと一致する"""
        result = _analysis(level1={"L1-01": _check()})
        rows = csv_writer.to_rows(result)

        for row in rows:
            assert len(row) == len(csv_writer.HEADER), f"Row has {len(row)} columns, expected {len(csv_writer.HEADER)}"

    def test_csv_violation_details_present(self):
        """CSVに違反箇所・違反内容・違反重大度が含まれる"""
        v = _violation(sheet="Sheet1", cell_range="A1:C1", description="結合セル", severity="error")
        result = _analysis(level1={"L1-12": _check(passed=False, violations=[v])})
        rows = csv_writer.to_rows(result)

        data_row = rows[1]
        header = csv_writer.HEADER
        loc_idx = header.index("違反箇所")
        desc_idx = header.index("違反内容")
        sev_idx = header.index("違反重大度")

        assert data_row[loc_idx] == "Sheet1!A1:C1"
        assert data_row[desc_idx] == "結合セル"
        assert data_row[sev_idx] == "error"

    def test_csv_multiple_violations_semicolon_separated(self):
        """複数違反がセミコロン区切りで結合される"""
        violations = [
            _violation(cell_range="A1", description="違反1", severity="error"),
            _violation(cell_range="B2", description="違反2", severity="warning"),
        ]
        result = _analysis(level1={"L1-12": _check(passed=False, violations=violations)})
        rows = csv_writer.to_rows(result)

        data_row = rows[1]
        header = csv_writer.HEADER
        loc_idx = header.index("違反箇所")
        desc_idx = header.index("違反内容")
        sev_idx = header.index("違反重大度")

        assert "Sheet1!A1" in data_row[loc_idx]
        assert "Sheet1!B2" in data_row[loc_idx]
        assert "; " in data_row[loc_idx]
        assert "違反1; 違反2" == data_row[desc_idx]
        assert "error; warning" == data_row[sev_idx]

    def test_csv_no_violations_empty_detail_columns(self):
        """違反なしの場合、違反詳細カラムが空文字"""
        result = _analysis(level1={"L1-01": _check(passed=True, violations=[])})
        rows = csv_writer.to_rows(result)

        data_row = rows[1]
        header = csv_writer.HEADER
        loc_idx = header.index("違反箇所")
        desc_idx = header.index("違反内容")
        sev_idx = header.index("違反重大度")

        assert data_row[loc_idx] == ""
        assert data_row[desc_idx] == ""
        assert data_row[sev_idx] == ""

    def test_csv_pass_fail_values(self):
        """合否が「合格」「不合格」で出力される"""
        result = _analysis(
            level1={
                "L1-01": _check(rule_id="L1-01", passed=True),
                "L1-12": _check(rule_id="L1-12", passed=False),
            },
        )
        rows = csv_writer.to_rows(result)

        header = csv_writer.HEADER
        status_idx = header.index("合否")
        statuses = {row[status_idx] for row in rows[1:]}
        assert statuses == {"合格", "不合格"}

    def test_csv_confidence_format(self):
        """信頼度が小数点2桁で出力される"""
        result = _analysis(level1={"L1-01": _check(confidence=0.9)})
        rows = csv_writer.to_rows(result)

        header = csv_writer.HEADER
        conf_idx = header.index("信頼度")
        assert rows[1][conf_idx] == "0.90"

    def test_csv_violation_count_matches_details(self):
        """違反数と違反詳細のセミコロン数が一致する"""
        violations = [_violation(cell_range=f"A{i}") for i in range(1, 4)]
        result = _analysis(level1={"L1-12": _check(passed=False, violations=violations)})
        rows = csv_writer.to_rows(result)

        data_row = rows[1]
        header = csv_writer.HEADER
        count_idx = header.index("違反数")
        loc_idx = header.index("違反箇所")

        count = int(data_row[count_idx])
        loc_parts = data_row[loc_idx].split("; ")
        assert count == len(loc_parts)

    def test_csv_string_valid_parse(self):
        """to_csv_stringの出力がCSVとして正しくパースできる"""
        result = _multi_sheet_analysis()
        csv_str = csv_writer.to_csv_string(result)

        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        # ヘッダー + 3ルール (L1-12, L2-01 from 売上 + L1-06 from 経費)
        assert len(rows) == 4
        assert rows[0] == csv_writer.HEADER

    def test_csv_multi_sheet_file_name_consistent(self):
        """複数シートでもファイル名が一貫している"""
        result = _multi_sheet_analysis()
        rows = csv_writer.to_rows(result)

        header = csv_writer.HEADER
        name_idx = header.index("ファイル名")
        for row in rows[1:]:
            assert row[name_idx] == "multi.xlsx"

    def test_csv_empty_analysis(self):
        """空のAnalysisResultではヘッダーのみ"""
        result = AnalysisResult(
            file_meta=FileMeta(name="empty.xlsx", sheet_count=0),
            sheets=[],
        )
        rows = csv_writer.to_rows(result)
        assert len(rows) == 1
        assert rows[0] == csv_writer.HEADER
