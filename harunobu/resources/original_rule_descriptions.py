"""ルール原本説明ローダー

デジタル庁の機械可読性チェックリスト原本の名称・説明文を
``original_rule_descriptions.json`` から読み込み、``RuleBase.original_description``
に提供する。

原本は ``docs/references/machine-readability-rules.json`` を出典とする
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import TypedDict


class OriginalRuleEntry(TypedDict):
    """原本チェックリスト 1 ルール分のエントリ（名称・説明・レベル）。"""

    name: str
    description: str
    level: str


_RESOURCE_NAME = "original_rule_descriptions.json"


@lru_cache(maxsize=1)
def load_original_rule_descriptions() -> dict[str, OriginalRuleEntry]:
    """``original_rule_descriptions.json`` をパースして返す。"""
    resource = files(__package__).joinpath(_RESOURCE_NAME)
    with resource.open("r", encoding="utf-8") as fp:
        data: dict[str, OriginalRuleEntry] = json.load(fp)
    return data
