"""AIVisualAnalyzer のテスト

AI/LibreOffice が利用できない環境でも全テストが通過するように設計。
モックで画像生成とAI呼び出しを差し替える。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from harunobu.core.ai_visual_analyzer import AIVisualAnalyzer


@pytest.fixture(autouse=True)
def reset_singleton():
    """各テスト前後にシングルトンをリセットする。"""
    AIVisualAnalyzer.reset_instance()
    yield
    AIVisualAnalyzer.reset_instance()


def make_mock_analyzer(
    mock_images: list[tuple[str, bytes]] | None = None,
    mock_ai_response: dict | list | None = None,
) -> AIVisualAnalyzer:
    """テスト用のモックアナライザーを生成する。"""
    analyzer = AIVisualAnalyzer()
    analyzer.is_available = MagicMock(return_value=True)  # type: ignore[method-assign]
    analyzer.capture_sheets = MagicMock(  # type: ignore[method-assign]
        return_value=mock_images or [("Sheet1", b"fake_png_data")]
    )
    analyzer._generate_with_image = MagicMock(return_value=mock_ai_response)  # type: ignore[method-assign]
    analyzer._generate_with_images = MagicMock(return_value=mock_ai_response)  # type: ignore[method-assign]
    return analyzer


def make_unavailable_analyzer() -> AIVisualAnalyzer:
    """AI unavailable なアナライザーを生成する。"""
    analyzer = AIVisualAnalyzer()
    analyzer.is_available = MagicMock(return_value=False)  # type: ignore[method-assign]
    return analyzer


class TestAIVisualAnalyzerAvailability:
    """is_available() のテスト"""

    def test_unavailable_when_disabled_env(self, monkeypatch):
        """HARUNOBU_AI_DISABLED=1 で unavailable"""
        monkeypatch.setenv("HARUNOBU_AI_DISABLED", "1")
        analyzer = AIVisualAnalyzer()
        assert analyzer.is_available() is False

    def test_singleton_returns_same_instance(self):
        """get_instance() が同一インスタンスを返す"""
        a = AIVisualAnalyzer.get_instance()
        b = AIVisualAnalyzer.get_instance()
        assert a is b

    def test_reset_instance_creates_new(self):
        """reset_instance() 後は新しいインスタンスが返される"""
        a = AIVisualAnalyzer.get_instance()
        AIVisualAnalyzer.reset_instance()
        b = AIVisualAnalyzer.get_instance()
        assert a is not b


class TestAnalyzeVisualLayout:
    """analyze_visual_layout() のテスト"""

    def test_unavailable_returns_empty(self):
        """AI unavailable で空結果"""
        analyzer = make_unavailable_analyzer()
        result = analyzer.analyze_visual_layout("/dummy/file.xlsx")
        assert result == {"sheets": [], "overall_quality": "unknown"}

    def test_returns_ai_analysis(self):
        """AI分析結果を返す"""
        mock_response = {
            "sheets": [
                {
                    "sheet_name": "Sheet1",
                    "tables_found": 1,
                    "has_color_coding": True,
                    "has_merged_headers": False,
                    "has_decorative_elements": False,
                    "has_annotations_outside_table": True,
                    "layout_description": "1つの表が配置",
                    "issues": [
                        {
                            "type": "color_coding",
                            "description": "セルの背景色で分類を表現",
                            "location": "B2:B10",
                        }
                    ],
                }
            ],
            "overall_quality": "fair",
        }
        analyzer = make_mock_analyzer(mock_ai_response=mock_response)
        result = analyzer.analyze_visual_layout("/dummy/file.xlsx")
        assert result["overall_quality"] == "fair"
        assert len(result["sheets"]) == 1
        assert result["sheets"][0]["has_color_coding"] is True

    def test_no_images_returns_empty(self):
        """画像生成失敗で空結果"""
        analyzer = make_mock_analyzer(mock_images=[])
        result = analyzer.analyze_visual_layout("/dummy/file.xlsx")
        assert result == {"sheets": [], "overall_quality": "unknown"}


class TestAnalyzeSheetVisual:
    """analyze_sheet_visual() のテスト"""

    def test_unavailable_returns_empty(self):
        """AI unavailable で空結果"""
        analyzer = make_unavailable_analyzer()
        result = analyzer.analyze_sheet_visual("/dummy/file.xlsx", "Sheet1")
        assert result["has_color_coding"] is False
        assert result["color_coded_cells"] == []

    def test_returns_detailed_analysis(self):
        """詳細な見た目分析を返す"""
        mock_response = {
            "has_color_coding": True,
            "color_coded_cells": [{"location": "B3", "color": "赤", "likely_meaning": "マイナス値"}],
            "has_merged_headers": True,
            "merged_areas": [{"location": "A1:D1", "description": "タイトル行の結合"}],
            "annotations": [{"location": "A20", "text": "注: 秘匿値は×で表示", "type": "footnote"}],
            "format_based_semantics": [{"location": "C5", "format_type": "bold", "likely_meaning": "合計行"}],
            "visual_issues": [],
        }
        analyzer = make_mock_analyzer(mock_ai_response=mock_response)
        result = analyzer.analyze_sheet_visual("/dummy/file.xlsx", "Sheet1")
        assert result["has_color_coding"] is True
        assert len(result["color_coded_cells"]) == 1
        assert result["color_coded_cells"][0]["color"] == "赤"
        assert result["has_merged_headers"] is True


class TestCheckFormatSemantics:
    """check_format_semantics() のテスト（L1-11 用）"""

    def test_unavailable_returns_empty(self):
        """AI unavailable で空リスト"""
        analyzer = make_unavailable_analyzer()
        result = analyzer.check_format_semantics("/dummy/file.xlsx", "Sheet1")
        assert result == []

    def test_detects_color_and_format_semantics(self):
        """色と書式の意味付けを検出"""
        mock_response = {
            "has_color_coding": True,
            "color_coded_cells": [
                {"location": "B3", "color": "赤", "likely_meaning": "マイナス値"},
                {"location": "D5:D10", "color": "グレー", "likely_meaning": "該当なし"},
            ],
            "has_merged_headers": False,
            "merged_areas": [],
            "annotations": [],
            "format_based_semantics": [{"location": "C5", "format_type": "bold", "likely_meaning": "合計行"}],
            "visual_issues": [],
        }
        analyzer = make_mock_analyzer(mock_ai_response=mock_response)
        result = analyzer.check_format_semantics("/dummy/file.xlsx", "Sheet1")
        assert len(result) == 3
        color_items = [r for r in result if r["format_type"] == "color"]
        assert len(color_items) == 2
        bold_items = [r for r in result if r["format_type"] == "bold"]
        assert len(bold_items) == 1


class TestCheckHeaderClarity:
    """check_header_clarity() のテスト（L1-05 用）"""

    def test_unavailable_returns_default(self):
        """AI unavailable でデフォルト"""
        analyzer = make_unavailable_analyzer()
        result = analyzer.check_header_clarity("/dummy/file.xlsx", "Sheet1")
        assert result["has_clear_headers"] is True
        assert result["confidence"] == 0.0

    def test_detects_merged_headers(self):
        """結合ヘッダーを検出"""
        mock_response = {
            "has_color_coding": False,
            "color_coded_cells": [],
            "has_merged_headers": True,
            "merged_areas": [{"location": "A1:C1", "description": "カテゴリヘッダーの結合"}],
            "annotations": [],
            "format_based_semantics": [],
            "visual_issues": [],
        }
        analyzer = make_mock_analyzer(mock_ai_response=mock_response)
        result = analyzer.check_header_clarity("/dummy/file.xlsx", "Sheet1")
        assert result["has_clear_headers"] is False
        assert result["has_multi_row_headers"] is True
        assert len(result["issues"]) == 1


class TestCaptureSheets:
    """capture_sheets() のテスト"""

    def test_cache_works(self):
        """同じファイルに対してキャッシュが効く"""
        analyzer = AIVisualAnalyzer()
        fake_images = [("Sheet1", b"png_data")]
        analyzer._convert_to_images = MagicMock(return_value=fake_images)  # type: ignore[method-assign]
        analyzer._get_soffice_path = MagicMock(return_value="/usr/bin/soffice")  # type: ignore[method-assign]

        # 1回目は変換が走る
        result1 = analyzer.capture_sheets("/dummy/file.xlsx")
        assert result1 == fake_images
        assert analyzer._convert_to_images.call_count == 1

        # 2回目はキャッシュヒット
        result2 = analyzer.capture_sheets("/dummy/file.xlsx")
        assert result2 == fake_images
        assert analyzer._convert_to_images.call_count == 1

    def test_no_soffice_returns_empty(self):
        """LibreOffice 未インストールで空リスト"""
        analyzer = AIVisualAnalyzer()
        analyzer._get_soffice_path = MagicMock(return_value=None)  # type: ignore[method-assign]
        result = analyzer.capture_sheets("/dummy/file.xlsx")
        assert result == []
