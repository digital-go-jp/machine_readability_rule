"""L2-05: 選択肢列と「その他」の詳細記入が分離されているかのテスト"""

from harunobu.core.models import ColumnSchema
from harunobu.rules.level2.L2_05_other_detail_separation import (
    OtherDetailSeparationRule,
)

# _MIN_BODY_ROWS=20 を満たすための通常選択肢
_CHOICES = ["1. 取組済", "2. 取組予定", "3. 未定"]
_PURE_OTHER = "4. その他"


def _rows(n_normal: int, *others: str) -> list[list]:
    """ヘッダー + n_normal 行の通常選択肢 + others の行を返す"""
    rows: list[list] = [["名前", "設問1"]]
    for i in range(n_normal):
        rows.append([f"名前{i:02d}", _CHOICES[i % 3]])
    for j, val in enumerate(others):
        rows.append([f"名前{n_normal + j:02d}", val])
    return rows


class TestOtherDetailSeparationCheck:
    """L2-05 「その他」詳細の分離チェック（決定論的）"""

    def test_separated_other_passes(self, create_context):
        """「その他」が1種類のみ（純粋な選択肢）なら違反なし"""
        # 「4. その他」が4件（≥ _OTHER_MIN_COUNT=3）→ 1種類しか存在しない → 条件1不成立
        ctx = create_context({"Sheet1": _rows(16, *[_PURE_OTHER] * 4)})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_other_with_parenthesis_detail_detected(self, create_context):
        """「その他（詳細）」パターンを統計的に検出する"""
        # 「4. その他」×3件（≥ _OTHER_MIN_COUNT → フラグされない）
        # 「その他（特に理由なし）」×2件（< _OTHER_MIN_COUNT → フラグ）
        ctx = create_context(
            {
                "Sheet1": _rows(
                    16, _PURE_OTHER, _PURE_OTHER, _PURE_OTHER, "4. その他（特に理由なし）", "4. その他（特に理由なし）"
                )
            }
        )
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is False
        assert any("その他" in v.description for v in result.violations)
        # 純粋な「4. その他」（3件）はフラグされない
        assert not any(
            "4. その他" in v.description
            and "4. その他（" not in v.description
            and v.description.count("4. その他") == 1
            and "可能性" not in v.description.split("4. その他")[1][:5]
            for v in result.violations
        ), "純粋な選択肢値「4. その他」は違反として記録されてはならない"

    def test_other_with_colon_detail_detected(self, create_context):
        """「その他：詳細」パターンを統計的に検出する"""
        ctx = create_context({"Sheet1": _rows(16, _PURE_OTHER, _PURE_OTHER, _PURE_OTHER, "その他：予算の問題")})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is False
        assert any("その他" in v.description for v in result.violations)

    def test_other_alone_passes(self, create_context):
        """「その他」が単独（詳細なし）で1種類のみなら違反なし"""
        # 「その他」×20件、1種類のみ → 条件1（2種類以上）不成立 → pass
        ctx = create_context({"Sheet1": _rows(0, *["その他"] * 20)})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_multiple_violations_detected(self, create_context):
        """複数の「その他+詳細」が混在する場合に全て検出する"""
        # 「4. その他」×3件（フラグなし）+ 詳細混在×3種（各1件、フラグあり）
        ctx = create_context(
            {
                "Sheet1": _rows(
                    14,
                    _PURE_OTHER,
                    _PURE_OTHER,
                    _PURE_OTHER,
                    "その他（時間がない）",
                    "その他：資金不足",
                    "その他（別の理由）",
                )
            }
        )
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is False
        assert len(result.violations) == 3

    def test_high_unique_count_column_skipped(self, create_context):
        """カーディナリティが閾値超過の列はスキップする"""
        # 21行すべてユニーク値 → unique > _MAX_CARDINALITY=20 → スキップ → 違反なし
        rows = [["名前", "意見"]] + [[f"人{i}", f"その他（意見{i}）"] for i in range(21)]
        ctx = create_context({"Sheet1": rows})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_few_rows_returns_low_confidence(self, create_context):
        """データ行数が _MIN_BODY_ROWS 未満の場合はチェックをスキップする"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "設問1"],
                    ["田中", "その他"],
                    ["鈴木", "その他（理由）"],
                    ["佐藤", "賛成"],
                    ["渡辺", "反対"],
                ]
            }
        )
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is True
        assert result.confidence == 0.0

    def test_numeric_column_skipped(self, create_context):
        """numeric と判定された列はスキップする"""
        ctx = create_context(
            {
                "Sheet1": [["名前", "金額"]] + [[f"名前{i:02d}", str(i * 100)] for i in range(21)],
            },
            column_schemas=[
                ColumnSchema(col_index=1, inferred_type="text"),
                ColumnSchema(col_index=2, inferred_type="numeric"),
            ],
        )
        result = OtherDetailSeparationRule().check(ctx)
        # 名前列は全ユニーク → cardinality超過でスキップ、数値列はnumericでスキップ
        assert result.passed is True
        assert result.confidence == 0.0

    def test_consistently_used_other_not_detected(self, create_context):
        """「その他の国」「その他の地域」が各3件以上→詳細混在とみなさない（FP防止）"""
        # 両値とも count ≥ _OTHER_MIN_COUNT=3 → フラグされない
        rows = (
            [["地域", "対象"]]
            + [[f"地域{i:02d}", "その他の国"] for i in range(10)]
            + [[f"地域{i:02d}", "その他の地域"] for i in range(10, 20)]
        )
        ctx = create_context({"Sheet1": rows})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_number_prefixed_other_detected(self, create_context):
        """「4. その他: 詳細」形式（旧正規表現で検出できなかったパターン）を検出する"""
        # 「4. その他」は "その他" を含む → other_values に入る
        # 「4. その他: 詳細内容」も "その他" を含む → 1件、count < 3 → flagged
        ctx = create_context(
            {
                "Sheet1": _rows(
                    16,
                    _PURE_OTHER,
                    _PURE_OTHER,
                    _PURE_OTHER,
                    "4. その他: 対象となる事務を他団体に委託しているため",
                )
            }
        )
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is False
        assert any("4. その他:" in v.description for v in result.violations)

    def test_leading_space_other_detected(self, create_context):
        """先頭スペース付き「 その他: 詳細」形式を検出する"""
        rows = (
            [["名前", "設問1"]]
            + [[f"名前{i:02d}", _CHOICES[i % 3]] for i in range(16)]
            + [
                [f"名前{i:02d}", " その他"]
                for i in range(16, 19)  # 3件
            ]
            + [
                ["名前19", " その他: 詳細内容"],  # 1件 → flagged
            ]
        )
        ctx = create_context({"Sheet1": rows})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is False
        assert any("その他:" in v.description for v in result.violations)

    def test_two_distinct_other_both_sufficient_count_passes(self, create_context):
        """2種類の「その他」値が両方 _OTHER_MIN_COUNT 以上なら違反なし"""
        # 条件2（count < 3）を満たさない → pass
        rows = (
            [["名前", "設問1"]]
            + [[f"名前{i:02d}", _CHOICES[i % 3]] for i in range(14)]
            + [
                [f"名前{i:02d}", "4. その他A"]
                for i in range(14, 17)  # 3件
            ]
            + [
                [f"名前{i:02d}", "4. その他B"]
                for i in range(17, 20)  # 3件
            ]
        )
        ctx = create_context({"Sheet1": rows})
        result = OtherDetailSeparationRule().check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0
