"""original_rule_descriptions ローダーのテスト"""

from __future__ import annotations

from harunobu.resources.original_rule_descriptions import load_original_rule_descriptions


class TestOriginalRuleDescriptions:
    def test_load_has_30_rules(self):
        data = load_original_rule_descriptions()
        assert len(data) == 30

    def test_rule_id_format(self):
        data = load_original_rule_descriptions()
        for rule_id in data:
            assert rule_id[0] == "L"
            assert rule_id[1] in {"1", "2", "3"}
            assert rule_id[2] == "-"

    def test_all_entries_have_non_empty_fields(self):
        data = load_original_rule_descriptions()
        for rule_id, entry in data.items():
            assert entry["name"], f"{rule_id}: name が空です"
            assert entry["description"], f"{rule_id}: description が空です"
            assert entry["level"], f"{rule_id}: level が空です"

    def test_level_is_valid(self):
        data = load_original_rule_descriptions()
        for rule_id, entry in data.items():
            assert entry["level"] in {"Level1", "Level2", "Level3"}, f"{rule_id}: 不正な level '{entry['level']}'"
