"""LayoutDetector — レイアウト検出のオーケストレータ (Strategy パターン)

Config.mode に応じて検出戦略を切り替える:
- lite: IslandDetector のみ
- standard: IslandDetector (将来的に追加戦略)
- thorough: 全戦略を実行し、最も信頼度の高い結果を採用
"""

from __future__ import annotations

import logging

from harunobu.core.layout.island import IslandDetector
from harunobu.core.models import Config, DetectionResult, Sheet, TableRegion

logger = logging.getLogger(__name__)


class LayoutDetector:
    """レイアウト検出のオーケストレータ。

    Strategy パターンで検出器を切り替える。
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._island_detector = IslandDetector()

    def detect(self, sheet: Sheet) -> list[TableRegion]:
        """シート内のテーブル領域を検出する。

        Args:
            sheet (Sheet): 対象シート

        Returns:
            list[TableRegion]: 検出されたテーブル領域のリスト（confidence 降順）
        """
        return self.detect_with_others(sheet).tables

    def detect_with_others(self, sheet: Sheet) -> DetectionResult:
        """シート内のテーブル領域と非テーブルセルを検出する。

        Args:
            sheet (Sheet): 対象シート

        Returns:
            DetectionResult: テーブル領域と非テーブルセルのリスト（テーブルは confidence 降順）
        """
        mode = self.config.mode

        if mode == "lite":
            detection = self._detect_lite_full(sheet)
        elif mode == "standard":
            detection = self._detect_standard_full(sheet)
        elif mode == "thorough":
            detection = self._detect_thorough_full(sheet)
        else:
            detection = self._detect_lite_full(sheet)

        regions = detection.tables
        others = detection.others

        # 信頼度閾値でフィルタリング
        threshold = self.config.confidence_threshold
        filtered = [r for r in regions if r.confidence >= threshold]

        # 信頼度の閾値未満の領域は abstain フラグを立てて含める
        for r in regions:
            if r.confidence < threshold:
                r.abstain = True
                filtered.append(r)

        # 信頼度降順でソート
        filtered.sort(key=lambda r: r.confidence, reverse=True)

        logger.debug(
            "LayoutDetector(%s): %d 領域検出 (sheet=%s)",
            mode,
            len(filtered),
            sheet.name,
        )
        return DetectionResult(tables=filtered, others=others)

    def _detect_lite(self, sheet: Sheet) -> list[TableRegion]:
        """lite モード: IslandDetector のみ。"""
        return self._island_detector.detect(sheet)

    def _detect_lite_full(self, sheet: Sheet) -> DetectionResult:
        """lite モード: IslandDetector のみ（DetectionResult版）。"""
        return self._island_detector.detect_with_others(sheet)

    def _detect_standard(self, sheet: Sheet) -> list[TableRegion]:
        """standard モード: IslandDetector + 将来の追加戦略。"""
        return self._island_detector.detect(sheet)

    def _detect_standard_full(self, sheet: Sheet) -> DetectionResult:
        """standard モード（DetectionResult版）。"""
        return self._island_detector.detect_with_others(sheet)

    def _detect_thorough(self, sheet: Sheet) -> list[TableRegion]:
        """thorough モード: 全戦略を実行し結果をマージ。"""
        return self._island_detector.detect(sheet)

    def _detect_thorough_full(self, sheet: Sheet) -> DetectionResult:
        """thorough モード（DetectionResult版）。"""
        return self._island_detector.detect_with_others(sheet)
