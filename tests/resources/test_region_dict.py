"""region_dict ローダーのテスト"""

from __future__ import annotations

from harunobu.resources.region_dict import (
    alias_to_municipality_name,
    load_region_dict,
    municipality_aliases,
    municipality_codes,
    municipality_names,
    prefecture_codes,
    prefecture_names,
    prefecture_short_names,
    short_to_prefecture_name,
)


class TestRegionDict:
    def test_load_region_dict_has_required_keys(self):
        data = load_region_dict()
        assert "version" in data
        assert "source" in data
        assert "prefectures" in data
        assert "municipalities" in data

    def test_47_prefectures(self):
        names = prefecture_names()
        assert len(names) == 47
        # サンプル確認
        assert "北海道" in names
        assert "東京都" in names
        assert "沖縄県" in names

    def test_prefecture_codes_are_2_digit_zero_padded(self):
        codes = prefecture_codes()
        assert len(codes) == 47
        for code in codes:
            assert len(code) == 2
            assert code.isdigit()
        assert "01" in codes
        assert "47" in codes

    def test_prefecture_short_names(self):
        shorts = prefecture_short_names()
        assert "東京" in shorts
        assert "大阪" in shorts
        assert "北海道" in shorts  # 北海道は例外で省略形 = 正式名

    def test_short_to_prefecture_name_mapping(self):
        mapping = short_to_prefecture_name()
        assert mapping["東京"] == "東京都"
        assert mapping["大阪"] == "大阪府"
        assert mapping["京都"] == "京都府"

    def test_municipality_names_has_minimum_volume(self):
        names = municipality_names()
        assert len(names) >= 100, f"市区町村は最低 100 件必要 (現在: {len(names)})"
        # 政令指定都市の代表例
        assert "札幌市" in names
        assert "横浜市" in names
        assert "大阪市" in names
        # 東京特別区の代表例
        assert "千代田区" in names
        assert "世田谷区" in names

    def test_municipality_aliases(self):
        aliases = municipality_aliases()
        assert "札幌" in aliases
        assert "横浜" in aliases

    def test_municipality_codes_are_6_digit(self):
        codes = municipality_codes()
        for code in codes:
            assert len(code) == 6
            assert code.isdigit()

    def test_municipality_pref_code_in_prefecture_codes(self):
        data = load_region_dict()
        pref_code_set = prefecture_codes()
        for muni in data["municipalities"]:
            assert muni["pref_code"] in pref_code_set, (
                f"未知の都道府県コード: {muni['pref_code']} (市区町村: {muni['name']})"
            )

    def test_no_duplicate_municipality_codes(self):
        data = load_region_dict()
        codes = [m["code"] for m in data["municipalities"]]
        assert len(codes) == len(set(codes)), "市区町村コードに重複があります"

    def test_no_duplicate_prefecture_codes(self):
        data = load_region_dict()
        codes = [p["code"] for p in data["prefectures"]]
        assert len(codes) == len(set(codes))

    def test_alias_to_municipality_name_mapping(self):
        mapping = alias_to_municipality_name()
        assert mapping.get("札幌") == "札幌市"
        # 「横浜」は横浜町（青森県、コード024066）と横浜市（神奈川県、コード141003）の両方がエイリアスに持つ。
        # setdefault はコード順で先に登録された横浜町を優先するため、「横浜市」にはならない。
        assert mapping.get("横浜") in {"横浜市", "横浜町"}
