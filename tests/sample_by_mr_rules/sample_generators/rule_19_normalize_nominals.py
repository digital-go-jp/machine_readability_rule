"""L2-04 用サンプル（選択肢回答が標準化されているか）。

OK:   No・設問1・設問1コードを持つアンケート（200行）。
      設問1は「取組済」「取組予定」「未定」で統一。
NG-01: 設問1に番号プレフィックス付きの表記揺れが混在
      （例: 「1. 取組済」「1. 取り組み済み」「2. 取組予定（R8以降）」）。
NG-02: 番号なしの表記揺れが混在
      （例: 「取組済み」「取り組み済」「取組予定である」「取組み予定」）。
"""

from __future__ import annotations

import random
from pathlib import Path

from .common import make_empty_workbook, save_workbook

_BASE_CHOICES = ["取組済", "取組予定", "未定"]
_CODE_MAP = {"取組済": 1, "取組予定": 2, "未定": 3}

# 表記揺れバリアント（番号付き）
_NG01_VARIANTS: dict[str, list[str]] = {
    "取組済": ["1. 取組済", "1. 取り組み済み", "1. 取組済み", "1. 取り組み済"],
    "取組予定": [
        "2. 取組予定",
        "2. 取組予定（R8以降）",
        "2. 取組予定である",
        "2. 取組み予定",
        "2. 取り組み予定",
        "2. 取組予定（令和9年以後、対象を分けて実施）",
    ],
    "未定": ["3. 未定"],
}

# 表記揺れバリアント（番号なし）
_NG02_VARIANTS: dict[str, list[str]] = {
    "取組済": ["取組済", "取り組み済み", "取組済み", "取り組み済"],
    "取組予定": [
        "取組予定",
        "取組予定（R8以降）",
        "取組予定である",
        "取組み予定",
        "取り組み予定",
        "取組予定（令和8年6月）",
    ],
    "未定": ["未定"],
}


def _generate_base_data(seed: int = 0) -> list[tuple[int, str, int]]:
    """200行分のベースデータ（No, 設問1, コード）をシード固定で生成。"""
    rng = random.Random(seed)
    rows = []
    for no in range(1, 201):
        choice = rng.choice(_BASE_CHOICES)
        rows.append((no, choice, _CODE_MAP[choice]))
    return rows


def _apply_variants(
    base_data: list[tuple[int, str, int]],
    variants: dict[str, list[str]],
    seed: int = 1,
) -> list[tuple[int, str]]:
    """ベースデータにバリアントを適用（一部のみ揺れを入れる）。"""
    rng = random.Random(seed)
    rows = []
    for no, choice, _ in base_data:
        options = variants[choice]
        # 「標準形」が最初の要素 — 70% は標準形、残り 30% でバリアントを使用
        if len(options) > 1 and rng.random() < 0.30:
            val = rng.choice(options[1:])
        else:
            val = options[0]
        rows.append((no, val))
    return rows


def _write_ok(ws, base_data: list[tuple[int, str, int]]) -> None:
    ws.cell(row=1, column=1, value="No")
    ws.cell(row=1, column=2, value="設問1")
    ws.cell(row=1, column=3, value="設問1コード")
    for i, (no, choice, code) in enumerate(base_data, start=2):
        ws.cell(row=i, column=1, value=no)
        ws.cell(row=i, column=2, value=choice)
        ws.cell(row=i, column=3, value=code)


def _write_ng(ws, ng_data: list[tuple[int, str]]) -> None:
    ws.cell(row=1, column=1, value="No")
    ws.cell(row=1, column=2, value="設問1")
    for i, (no, val) in enumerate(ng_data, start=2):
        ws.cell(row=i, column=1, value=no)
        ws.cell(row=i, column=2, value=val)


def generate(output_dir: Path) -> list[Path]:
    base_data = _generate_base_data(seed=0)

    workbook, ok_sheet = make_empty_workbook(first_sheet_title="OK")
    _write_ok(ok_sheet, base_data)

    ng01_data = _apply_variants(base_data, _NG01_VARIANTS, seed=1)
    ws_ng01 = workbook.create_sheet("NG-01")
    _write_ng(ws_ng01, ng01_data)

    ng02_data = _apply_variants(base_data, _NG02_VARIANTS, seed=2)
    ws_ng02 = workbook.create_sheet("NG-02")
    _write_ng(ws_ng02, ng02_data)

    return [save_workbook(output_dir, workbook, "rule_19_normalize_nominals")]
