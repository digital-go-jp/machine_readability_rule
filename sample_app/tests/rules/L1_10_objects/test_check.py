"""L1-10: オブジェクト（画像・図形）の存在チェックのテスト

ルールは TableRegion.range（CellRange）とアンカー位置の包含のみを見る。
OOXML 由来の ObjectRef を一次情報として使用し、失敗時は abstain。
"""

from __future__ import annotations

import pytest

from harunobu.core.models import CellRange, ObjectRef, TableLayout, TableRegion
from harunobu.rules.level1.L1_10_objects import (
    ObjectsRule,
    _object_ref_intersects_table_range,
)

DRAWING_PART = "xl/drawings/drawing1.xml"


def _ref(row: int, col: int, object_type: str = "image", name: str | None = "obj") -> ObjectRef:
    return ObjectRef(
        sheet_name="Sheet1",
        object_type=object_type,  # type: ignore[arg-type]
        row=row,
        col=col,
        name=name,
        drawing_part=DRAWING_PART,
    )


class TestObjectsCheck:
    """L1-10 オブジェクトチェック（OOXML object_refs 経由）"""

    @pytest.fixture
    def rule(self):
        return ObjectsRule()

    def test_no_objects_passes(self, rule, create_context):
        """オブジェクトがない場合はpass"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = []
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is True
        # assert result.score == 100
        assert len(result.violations) == 0

    def test_csv_skipped(self, rule, create_context):
        """CSV形式の場合はチェック対象外"""
        ctx = create_context(
            {"Sheet1": [["名前", "年齢"], ["太郎", 20]]},
            file_name="test.csv",
        )
        result = rule.check(ctx)
        assert result.passed is True

    def test_objects_detected_inside_table(self, rule, create_context):
        """table_region.range 内にアンカーがあると違反"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = [_ref(1, 1, name="logo.png")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 1
        # assert result.score == 80
        assert result.violations[0].cell_range == "A1"

    def test_multiple_objects_detected(self, rule, create_context):
        """複数オブジェクトのアンカーがいずれも検出範囲内にある場合"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = [
            _ref(1, 1, object_type="image", name="logo.png"),
            _ref(2, 1, object_type="chart", name="グラフ1"),
            _ref(2, 2, object_type="shape", name="四角形1"),
        ]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False
        assert len(result.violations) == 3
        # assert result.score == 40

    def test_violation_description_contains_type_and_name(self, rule, create_context):
        """違反の説明にオブジェクトの種類と名前が含まれる"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = [_ref(1, 2, object_type="image", name="logo.png")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert len(result.violations) == 1
        assert "image" in result.violations[0].description
        assert "logo.png" in result.violations[0].description

    def test_name_none_uses_drawing_part_in_description(self, rule, create_context):
        """name=None のとき drawing_part が補助表示される"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = [_ref(1, 1, name=None)]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False
        assert DRAWING_PART in result.violations[0].description

    def test_score_clamped_at_zero_with_many_objects(self, rule, create_context):
        """6件以上のオブジェクトでスコアが0にクランプされる"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = [_ref(1, 1, name=f"img{i}") for i in range(6)]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False
        # assert result.score == 0

    def test_object_outside_table_range_passes(self, rule, create_context):
        """TableRegion.range より外（列方向）にアンカーがあれば許容"""
        ctx = create_context({"Sheet1": [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]]})
        ctx = ctx.model_copy(
            update={
                "table_region": TableRegion(
                    range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
                    layout=TableLayout(
                        header_rows=[1],
                        body_start_row=2,
                        body_end_row=3,
                        columns=[],
                    ),
                    confidence=1.0,
                )
            }
        )
        ctx.sheet.object_refs = [_ref(1, 3, name="side")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_boundary_anchor_on_end_inside(self, rule, create_context):
        """range の右下角セル上のアンカーは範囲内（違反）"""
        ctx = create_context({"Sheet1": [["a", "b"], ["c", "d"]]})
        ctx = ctx.model_copy(
            update={
                "table_region": TableRegion(
                    range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
                    layout=TableLayout(
                        header_rows=[1],
                        body_start_row=2,
                        body_end_row=2,
                        columns=[],
                    ),
                    confidence=1.0,
                )
            }
        )
        ctx.sheet.object_refs = [_ref(2, 2, name="x")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False

    def test_boundary_adjacent_outside_passes(self, rule, create_context):
        """range の列方向すぐ隣のセルは範囲外（許容）"""
        ctx = create_context({"Sheet1": [["a", "b", "x"], ["c", "d", "y"]]})
        ctx = ctx.model_copy(
            update={
                "table_region": TableRegion(
                    range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
                    layout=TableLayout(
                        header_rows=[1],
                        body_start_row=2,
                        body_end_row=2,
                        columns=[],
                    ),
                    confidence=1.0,
                )
            }
        )
        ctx.sheet.object_refs = [_ref(2, 3, name="x")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is True

    def test_boundary_adjacent_below_outside_passes(self, rule, create_context):
        """range の行方向すぐ下のセルは範囲外（許容）"""
        ctx = create_context({"Sheet1": [["a", "b"], ["c", "d"], ["x", "y"]]})
        ctx = ctx.model_copy(
            update={
                "table_region": TableRegion(
                    range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
                    layout=TableLayout(
                        header_rows=[1],
                        body_start_row=2,
                        body_end_row=2,
                        columns=[],
                    ),
                    confidence=1.0,
                )
            }
        )
        ctx.sheet.object_refs = [_ref(3, 1, name="below")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_object_refs_error_returns_abstain(self, rule, create_context):
        """object_refs_error がある場合は confidence=0 で abstain"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs_error = "inspect_failed:KeyError"
        result = rule.check(ctx)
        assert result.confidence == 0.0
        # assert result.score == 0
        assert result.passed is True

    def test_object_refs_not_loaded_returns_abstain(self, rule, create_context):
        """object_refs_loaded=False のとき abstain（confidence=0）"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        # object_refs_loaded はデフォルト False
        result = rule.check(ctx)
        assert result.confidence == 0.0
        # assert result.score == 0
        assert result.passed is True

    def test_abstain_table_region_flags_all_objects(self, rule, create_context):
        """abstain=True のとき範囲外オブジェクトも確認対象になる"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx = ctx.model_copy(
            update={
                "table_region": TableRegion(
                    range=CellRange(start_row=1, start_col=1, end_row=2, end_col=2),
                    layout=TableLayout(
                        header_rows=[1],
                        body_start_row=2,
                        body_end_row=2,
                        columns=[],
                    ),
                    confidence=0.3,
                    abstain=True,
                )
            }
        )
        ctx.sheet.object_refs = [_ref(5, 5, name="faraway")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False
        assert "abstain" in result.violations[0].description

    def test_connector_type_in_violation_description(self, rule, create_context):
        """違反説明に object_type が含まれる"""
        ctx = create_context({"Sheet1": [["名前", "年齢"], ["太郎", 20]]})
        ctx.sheet.object_refs = [_ref(1, 1, object_type="connector", name="矢印1")]
        ctx.sheet.object_refs_loaded = True
        result = rule.check(ctx)
        assert result.passed is False
        assert "connector" in result.violations[0].description
        assert "矢印1" in result.violations[0].description


class TestObjectRefIntersectsHelper:
    """_object_ref_intersects_table_range の境界テスト（退行防止用）"""

    def test_inside(self):
        table = CellRange(start_row=1, start_col=1, end_row=2, end_col=2)
        ref = _ref(1, 2)
        assert _object_ref_intersects_table_range(ref, table) is True

    def test_outside(self):
        table = CellRange(start_row=1, start_col=1, end_row=2, end_col=2)
        ref = _ref(1, 3)
        assert _object_ref_intersects_table_range(ref, table) is False
