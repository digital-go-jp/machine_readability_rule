"""都道府県・市区町村辞書ローダー

JIS X 0401（都道府県コード）/ JIS X 0402（市区町村コード）に基づく辞書を
``region_dict.json`` から読み込み、L3-06 ルールなどに提供する。

辞書は ``@lru_cache`` で 1 回だけパースされる。更新フローは
``script/update_region_dict.py`` を参照。
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import TypedDict


class PrefectureEntry(TypedDict):
    """都道府県 1 件分のエントリ（コード・正式名称・カナ・省略形）。"""

    code: str
    name: str
    kana: str
    short: str


class MunicipalityEntry(TypedDict):
    """市区町村 1 件分のエントリ（コード・所属都道府県コード・名称・カナ・別名）。"""

    code: str
    pref_code: str
    name: str
    kana: str
    aliases: list[str]


class RegionDict(TypedDict):
    """地域辞書全体（バージョン・出典・都道府県および市区町村のリスト）。"""

    version: str
    source: str
    prefectures: list[PrefectureEntry]
    municipalities: list[MunicipalityEntry]


_RESOURCE_NAME = "region_dict.json"


@lru_cache(maxsize=1)
def load_region_dict() -> RegionDict:
    """``region_dict.json`` をパースして返す。"""
    resource = files(__package__).joinpath(_RESOURCE_NAME)
    with resource.open("r", encoding="utf-8") as fp:
        data: RegionDict = json.load(fp)
    return data


@lru_cache(maxsize=1)
def prefecture_names() -> frozenset[str]:
    """正式な都道府県名の集合（例: ``{"北海道", "青森県", ...}``）。"""
    return frozenset(p["name"] for p in load_region_dict()["prefectures"])


@lru_cache(maxsize=1)
def prefecture_short_names() -> frozenset[str]:
    """都道府県の省略形の集合（例: ``{"北海道", "青森", "東京", ...}``）。"""
    return frozenset(p["short"] for p in load_region_dict()["prefectures"])


@lru_cache(maxsize=1)
def prefecture_codes() -> frozenset[str]:
    """JIS X 0401 都道府県コード（2桁）の集合。"""
    return frozenset(p["code"] for p in load_region_dict()["prefectures"])


@lru_cache(maxsize=1)
def municipality_names() -> frozenset[str]:
    """正式な市区町村名の集合（例: ``{"札幌市", "横浜市", ...}``）。"""
    return frozenset(m["name"] for m in load_region_dict()["municipalities"])


@lru_cache(maxsize=1)
def municipality_aliases() -> frozenset[str]:
    """市区町村の省略形・別名の集合（例: ``{"札幌", "横浜", ...}``）。"""
    aliases: set[str] = set()
    for m in load_region_dict()["municipalities"]:
        aliases.update(m["aliases"])
    return frozenset(aliases)


@lru_cache(maxsize=1)
def municipality_codes() -> frozenset[str]:
    """JIS X 0402 市区町村コード（6桁、チェックデジット込み）の集合。"""
    return frozenset(m["code"] for m in load_region_dict()["municipalities"])


@lru_cache(maxsize=1)
def alias_to_municipality_name() -> dict[str, str]:
    """エイリアス → 正式名称の写像（重複時は最初に登録された名前を採用）。"""
    mapping: dict[str, str] = {}
    for m in load_region_dict()["municipalities"]:
        for alias in m["aliases"]:
            mapping.setdefault(alias, m["name"])
    return mapping


@lru_cache(maxsize=1)
def short_to_prefecture_name() -> dict[str, str]:
    """都道府県の省略形 → 正式名称の写像。"""
    return {p["short"]: p["name"] for p in load_region_dict()["prefectures"]}
