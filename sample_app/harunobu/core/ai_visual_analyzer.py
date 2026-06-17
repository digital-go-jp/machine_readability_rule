"""AIビジュアルアナライザー - Excel/CSVの見た目からの分析

LibreOffice で Excel/CSV ファイルを画像に変換し、
LLM のマルチモーダル機能で見た目から判断する。
AIClient 経由で Gemini / OpenAI / Anthropic 等の任意プロバイダーを利用可能。

見た目からしか分からない情報:
- 色・背景色による意味付け（L1-11）
- 罫線による表の区切り
- セルの幅・高さによるレイアウト意図
- 印刷用の装飾（ヘッダー/フッター）
- 注釈テキストの配置
- 全体のレイアウト構造（余白、複数表の配置）
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_SOFFICE_PATHS = [
    "/opt/homebrew/bin/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def _find_soffice() -> str | None:
    """LibreOffice (soffice) のパスを見つける。"""
    # PATH から検索
    result = shutil.which("soffice")
    if result:
        return result
    # 既知のパスを順に確認
    for path in _SOFFICE_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


class AIVisualAnalyzer:
    """Excel/CSV ファイルの見た目を AI で分析する。

    シングルトンパターン。LibreOffice + LLM（AIClient 経由）。
    AI や LibreOffice が利用できない場合は graceful fallback する。
    """

    _instance: AIVisualAnalyzer | None = None
    _screenshot_cache: dict[str, list[tuple[str, bytes]]] = {}

    @classmethod
    def get_instance(cls) -> AIVisualAnalyzer:
        """シングルトンインスタンスを返す（未生成なら生成）。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """テスト用: インスタンスをリセットする。"""
        cls._instance = None
        cls._screenshot_cache = {}

    def __init__(self) -> None:
        self._available: bool | None = None
        self._soffice_path: str | None = None

    def is_available(self) -> bool:
        """AI + LibreOffice が利用可能かチェックする。"""
        if os.environ.get("HARUNOBU_AI_DISABLED", "").lower() in ("1", "true", "yes"):
            return False
        if self._available is not None:
            return self._available
        try:
            from harunobu.core.ai_client import AIClient

            if not AIClient.get_instance().is_available():
                self._available = False
                return False
            soffice = self._get_soffice_path()
            self._available = soffice is not None
        except Exception as e:
            self._available = False
            logger.debug("Visual analyzer not available: %s", e)
        return self._available

    def _get_soffice_path(self) -> str | None:
        if self._soffice_path is None:
            self._soffice_path = _find_soffice()
        return self._soffice_path

    def _generate_with_image(
        self, prompt: str, image_data: bytes, mime_type: str = "image/png", *, method_name: str = "visual_unknown"
    ) -> Any | None:
        """画像付きで AI を呼び出して JSON を生成する。"""
        if not self.is_available():
            return None
        from harunobu.core.ai_client import AIClient

        return AIClient.get_instance().generate_json_with_image(prompt, image_data, mime_type, method_name=method_name)

    def _generate_with_images(
        self, prompt: str, images: list[tuple[str, bytes]], *, method_name: str = "visual_multi_unknown"
    ) -> Any | None:
        """複数画像付きで AI を呼び出して JSON を生成する。"""
        if not self.is_available():
            return None
        from harunobu.core.ai_client import AIClient

        return AIClient.get_instance().generate_json_with_images(prompt, images, method_name=method_name)

    # ─── スクリーンショット取得 ─────────────────────────────────────────

    def capture_sheets(self, file_path: str) -> list[tuple[str, bytes]]:
        """Excel/CSV ファイルの各シートを PNG 画像に変換する。

        LibreOffice を使って PDF 経由で画像を生成する。
        結果はファイルパスごとにキャッシュする。

        Returns:
            list[tuple[str, bytes]]: ``(sheet_name, png_bytes)`` のリスト
        """
        cache_key = self._cache_key(file_path)
        if cache_key in self._screenshot_cache:
            return self._screenshot_cache[cache_key]

        soffice = self._get_soffice_path()
        if soffice is None:
            logger.warning("LibreOffice not found, visual analysis unavailable")
            return []

        images = self._convert_to_images(file_path, soffice)
        self._screenshot_cache[cache_key] = images
        return images

    def _cache_key(self, file_path: str) -> str:
        """ファイルパスとmtimeからキャッシュキーを生成する。"""
        try:
            mtime = os.path.getmtime(file_path)
            return hashlib.md5(f"{file_path}:{mtime}".encode()).hexdigest()
        except OSError:
            return hashlib.md5(file_path.encode()).hexdigest()

    def _convert_to_images(self, file_path: str, soffice: str) -> list[tuple[str, bytes]]:
        """LibreOffice で Excel を PNG に変換する。"""
        images: list[tuple[str, bytes]] = []

        with tempfile.TemporaryDirectory(prefix="harunobu_visual_") as tmpdir:
            tmpdir_path = Path(tmpdir)

            # LibreOffice で PNG に変換（各シートが個別PNGになる）
            try:
                result = subprocess.run(
                    [
                        soffice,
                        "--headless",
                        "--convert-to",
                        "png",
                        "--outdir",
                        str(tmpdir_path),
                        file_path,
                    ],
                    capture_output=True,
                    timeout=60,
                    env={**os.environ, "HOME": tmpdir},  # LibreOffice のロックファイル問題回避
                )
                if result.returncode != 0:
                    logger.warning("LibreOffice conversion failed: %s", result.stderr.decode(errors="replace"))
                    return []
            except subprocess.TimeoutExpired:
                logger.warning("LibreOffice conversion timed out for %s", file_path)
                return []
            except Exception as e:
                logger.warning("LibreOffice conversion error: %s", e)
                return []

            # 生成された PNG を読み込む
            png_files = sorted(tmpdir_path.glob("*.png"))
            if not png_files:
                # PNG がない場合は PDF 経由で試行
                images = self._convert_via_pdf(file_path, soffice, tmpdir_path)
                if images:
                    return images
                logger.debug("No PNG files generated for %s", file_path)
                return []

            # シート名の推定（LibreOffice はファイル名ベースで出力）
            for i, png_file in enumerate(png_files):
                sheet_name = self._infer_sheet_name(file_path, i, png_file.stem)
                try:
                    png_bytes = png_file.read_bytes()
                    if png_bytes:
                        images.append((sheet_name, png_bytes))
                except Exception as e:
                    logger.debug("Failed to read PNG %s: %s", png_file, e)

        return images

    def _convert_via_pdf(self, file_path: str, soffice: str, tmpdir_path: Path) -> list[tuple[str, bytes]]:
        """PDF 経由で画像変換を試みる（フォールバック）。"""
        images: list[tuple[str, bytes]] = []

        try:
            # まず PDF に変換
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmpdir_path),
                    file_path,
                ],
                capture_output=True,
                timeout=60,
                env={**os.environ, "HOME": str(tmpdir_path)},
            )
            if result.returncode != 0:
                return []

            pdf_files = list(tmpdir_path.glob("*.pdf"))
            if not pdf_files:
                return []

            # PDF の各ページを PNG に変換
            pdf_path = pdf_files[0]

            # pdftoppm が利用可能か確認
            pdftoppm = shutil.which("pdftoppm")
            if pdftoppm:
                subprocess.run(
                    [pdftoppm, "-png", "-r", "150", str(pdf_path), str(tmpdir_path / "sheet")],
                    capture_output=True,
                    timeout=60,
                )
                for i, png_file in enumerate(sorted(tmpdir_path.glob("sheet-*.png"))):
                    sheet_name = self._infer_sheet_name(file_path, i, png_file.stem)
                    try:
                        images.append((sheet_name, png_file.read_bytes()))
                    except Exception:
                        pass
            else:
                # pdftoppm がなければ PDF を直接 Gemini に渡すため、PDF バイトを保持
                # （この場合は画像として扱わない）
                logger.debug("pdftoppm not available, PDF fallback skipped")

        except Exception as e:
            logger.debug("PDF conversion failed: %s", e)

        return images

    def _infer_sheet_name(self, file_path: str, index: int, png_stem: str) -> str:
        """PNG ファイル名からシート名を推定する。"""
        # openpyxl でシート名一覧を取得（高速、データ読み込みなし）
        try:
            if file_path.endswith(".xlsx"):
                import openpyxl

                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                sheet_names = wb.sheetnames
                wb.close()
                if index < len(sheet_names):
                    return sheet_names[index]
        except Exception:
            pass

        return f"Sheet{index + 1}"

    # ─── ビジュアル分析 API ─────────────────────────────────────────

    def analyze_visual_layout(self, file_path: str) -> dict:
        """ファイル全体の見た目からレイアウト・構造を分析する。

        Returns:
            dict: 次の構造の辞書::

                {
                "sheets": [
                {
                "sheet_name": str,
                "tables_found": int,
                "has_color_coding": bool,
                "has_merged_headers": bool,
                "has_decorative_elements": bool,
                "has_annotations_outside_table": bool,
                "layout_description": str,
                "issues": [{"type": str, "description": str, "location": str}],
                }
                ],
                "overall_quality": str,
                }
        """
        if not self.is_available():
            return {"sheets": [], "overall_quality": "unknown"}

        images = self.capture_sheets(file_path)
        if not images:
            return {"sheets": [], "overall_quality": "unknown"}

        prompt = """以下はExcelファイルの各シートのスクリーンショットです。
各シートの見た目から以下を分析してください。

行政データの機械可読性の観点で問題を検出してください:
1. 色・背景色で意味を持たせているセルがあるか（色がないと意味が分からなくなる）
2. セルの結合が使われているか（特にヘッダー部分）
3. 表の外に注釈・脚注・メモが配置されているか
4. 装飾的な要素（ロゴ、画像、罫線装飾）があるか
5. 複数の表が1シートに配置されているか
6. 印刷用レイアウト（タイトル行、余白、ページ区切り）が見えるか
7. 空白行・空白列で区切られたセクション構造
8. ヘッダー行が複数行にまたがっているか

JSON回答:
{
    "sheets": [
        {
            "sheet_name": "シート名",
            "tables_found": 1,
            "has_color_coding": false,
            "has_merged_headers": false,
            "has_decorative_elements": false,
            "has_annotations_outside_table": false,
            "layout_description": "表の配置や構造の説明",
            "issues": [
                {"type": "color_coding", "description": "問題の詳細", "location": "セル範囲やエリアの説明"}
            ]
        }
    ],
    "overall_quality": "good/fair/poor"
}"""

        result = self._generate_with_images(prompt, images, method_name="analyze_workbook_visual")
        if result is None or not isinstance(result, dict):
            return {"sheets": [], "overall_quality": "unknown"}
        return result

    def analyze_sheet_visual(
        self,
        file_path: str,
        sheet_name: str,
    ) -> dict:
        """特定シートの見た目を分析する。

        Returns:
            dict: 次の構造の辞書::

                {
                "has_color_coding": bool,
                "color_coded_cells": [{"location": str, "color": str, "likely_meaning": str}],
                "has_merged_headers": bool,
                "merged_areas": [{"location": str, "description": str}],
                "annotations": [{"location": str, "text": str, "type": str}],
                "format_based_semantics": [{"location": str, "format_type": str, "likely_meaning": str}],
                "visual_issues": [{"type": str, "description": str, "severity": str}],
                }
        """
        if not self.is_available():
            return self._empty_sheet_analysis()

        images = self.capture_sheets(file_path)
        target_image = None
        for name, data in images:
            if name == sheet_name:
                target_image = data
                break

        # シート名が一致しない場合はインデックスで試行
        if target_image is None and images:
            try:
                if file_path.endswith(".xlsx"):
                    import openpyxl

                    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                    idx = list(wb.sheetnames).index(sheet_name)
                    wb.close()
                    if idx < len(images):
                        target_image = images[idx][1]
            except Exception:
                pass

        if target_image is None:
            # 最初の画像をフォールバックとして使用
            if images:
                target_image = images[0][1]
            else:
                return self._empty_sheet_analysis()

        prompt = f"""以下はExcelファイルの「{sheet_name}」シートのスクリーンショットです。
見た目から以下を詳細に分析してください。

行政データの機械可読性チェック観点:

1. **色による意味付け**: 背景色やフォント色で情報を伝えているセルを特定してください。
   例: 赤字で「マイナス」、グレー背景で「該当なし」、黄色で「要注意」等

2. **結合セル**: ヘッダーやデータ領域で結合されているセルを特定してください。

3. **書式ベース意味付け**: 太字・斜体・取り消し線等で意味を持たせている箇所

4. **表外の注釈**: 表の外に配置されたメモ、脚注、注意書き

5. **装飾要素**: ロゴ、画像、罫線アート、空白セルでの余白作り

6. **レイアウト問題**: 表の開始位置が不自然（A1以外から始まる等）

JSON回答:
{{
    "has_color_coding": true/false,
    "color_coded_cells": [
        {{"location": "セル位置や範囲", "color": "色の説明", "likely_meaning": "推定される意味"}}
    ],
    "has_merged_headers": true/false,
    "merged_areas": [
        {{"location": "セル範囲", "description": "結合の説明"}}
    ],
    "annotations": [
        {{"location": "位置", "text": "注釈テキスト", "type": "footnote/comment/note"}}
    ],
    "format_based_semantics": [
        {{"location": "セル位置", "format_type": "bold/italic/color/strikethrough", "likely_meaning": "意味"}}
    ],
    "visual_issues": [
        {{"type": "issue_type", "description": "問題の説明", "severity": "error/warning/info"}}
    ]
}}"""

        result = self._generate_with_image(prompt, target_image, method_name="analyze_sheet_visual")
        if result is None or not isinstance(result, dict):
            return self._empty_sheet_analysis()
        return result

    def check_format_semantics(
        self,
        file_path: str,
        sheet_name: str,
    ) -> list[dict]:
        """見た目から書式ベースの意味付けを検出する（L1-11 用）。

        Returns:
            list[dict]: ``{"location": str, "format_type": str, "meaning": str, "confidence": float}`` のリスト
        """
        if not self.is_available():
            return []

        analysis = self.analyze_sheet_visual(file_path, sheet_name)
        results = []

        # 色による意味付け
        for item in analysis.get("color_coded_cells", []):
            results.append(
                {
                    "location": item.get("location", ""),
                    "format_type": "color",
                    "meaning": item.get("likely_meaning", ""),
                    "confidence": 0.8,
                }
            )

        # 書式ベース意味付け
        for item in analysis.get("format_based_semantics", []):
            results.append(
                {
                    "location": item.get("location", ""),
                    "format_type": item.get("format_type", ""),
                    "meaning": item.get("likely_meaning", ""),
                    "confidence": 0.75,
                }
            )

        return results

    def check_header_clarity(
        self,
        file_path: str,
        sheet_name: str,
    ) -> dict:
        """見た目からヘッダーの明確さを評価する（L1-05 用）。

        Returns:
            dict: 次の構造の辞書::

                {
                "has_clear_headers": bool,
                "has_multi_row_headers": bool,
                "issues": [{"description": str, "location": str}],
                "confidence": float,
                }
        """
        if not self.is_available():
            return {
                "has_clear_headers": True,
                "has_multi_row_headers": False,
                "issues": [],
                "confidence": 0.0,
            }

        analysis = self.analyze_sheet_visual(file_path, sheet_name)
        has_merged = analysis.get("has_merged_headers", False)

        issues = []
        for area in analysis.get("merged_areas", []):
            issues.append(
                {
                    "description": area.get("description", ""),
                    "location": area.get("location", ""),
                }
            )

        return {
            "has_clear_headers": not has_merged and len(issues) == 0,
            "has_multi_row_headers": has_merged,
            "issues": issues,
            "confidence": 0.75 if analysis else 0.0,
        }

    @staticmethod
    def _empty_sheet_analysis() -> dict:
        return {
            "has_color_coding": False,
            "color_coded_cells": [],
            "has_merged_headers": False,
            "merged_areas": [],
            "annotations": [],
            "format_based_semantics": [],
            "visual_issues": [],
        }
