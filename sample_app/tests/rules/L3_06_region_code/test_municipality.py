"""L3-06: 市区町村名対応のテスト"""

from __future__ import annotations

from harunobu.rules.level3.L3_06_region_code import RegionCodeRule


class TestMunicipalityDetection:
    """市区町村名による地域列の検出と省略形チェック"""

    def test_municipality_only_column_detected_as_region(self, create_context):
        """市区町村名のみの列でも地域列として検出される（ヘッダーキーワードなし）"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名称", "人口"],
                    ["札幌市", 1970000],
                    ["横浜市", 3770000],
                    ["大阪市", 2750000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        # 地域列として検出されたら、コード列がないため info 違反が1件出る
        assert len(result.violations) <= 1
        # 省略違反は出ないはず（すべて正式名称）
        assert not any("省略" in v.description for v in result.violations)

    def test_municipality_abbreviation_detected(self, create_context):
        """「札幌」（市抜き）が省略形 warning として検出される"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["市区町村", "人口"],
                    ["札幌", 1970000],
                    ["横浜", 3770000],
                    ["大阪", 2750000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        # 省略形違反が出る
        assert result.passed is False
        assert any("省略" in v.description for v in result.violations)

    def test_full_municipality_name_with_code_passes(self, create_context):
        """正式な市区町村名と団体コード列がある場合はパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["団体コード", "市区町村", "人口"],
                    ["011002", "札幌市", 1970000],
                    ["141003", "横浜市", 3770000],
                    ["271004", "大阪市", 2750000],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_municipality_alias_warning_severity(self, create_context):
        """市区町村省略形違反は severity=warning"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["市区町村", "値"],
                    ["札幌", 100],
                    ["横浜", 200],
                ],
            },
        )
        rule = RegionCodeRule()
        result = rule.check(ctx)
        muni_violations = [v for v in result.violations if "市区町村" in v.description]
        assert len(muni_violations) >= 1
        for v in muni_violations:
            assert v.severity == "warning"
