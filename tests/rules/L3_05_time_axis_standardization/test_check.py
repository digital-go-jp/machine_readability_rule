"""L3-05: 時間軸の表記が標準化されているかのテスト"""

from harunobu.rules.level3.L3_05_time_axis_standardization import (
    TimeAxisStandardizationRule,
)


class TestTimeAxisStandardizationCheck:
    """L3-05 時間軸表記の標準化チェック"""

    def test_seireki_dates_passes(self, create_context):
        """西暦表記で統一されている場合に違反なし"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年月"],
                    ["太郎", "2023年4月"],
                    ["花子", "2023年5月"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_wareki_in_data_detected(self, create_context):
        """データ行に和暦表記がある場合に違反を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年月"],
                    ["太郎", "令和5年4月"],
                    ["花子", "令和5年5月"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("和暦" in v.description for v in result.violations)

    def test_wareki_in_header_detected(self, create_context):
        """ヘッダーに和暦表記がある場合に違反を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "令和3年", "令和4年"],
                    ["太郎", 100, 200],
                    ["花子", 150, 250],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("和暦" in v.description for v in result.violations)

    def test_nendo_notation_passes(self, create_context):
        """年度表記（西暦）は標準表記としてパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年度"],
                    ["太郎", "2022年度"],
                    ["花子", "2023年度"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is True

    def test_nonstandard_date_notation_detected(self, create_context):
        """`03/04/01` のような曖昧な 2 桁年表記を非標準として検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日付"],
                    ["太郎", "03/04/01"],
                    ["花子", "03/05/01"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("非標準" in v.description for v in result.violations)

    def test_mixed_formats_detected(self, create_context):
        """同一列内での日付フォーマット混在を検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "年月"],
                    ["太郎", "2023年4月"],
                    ["花子", "令和5年5月"],  # 和暦混入
                    ["次郎", "2023年6月"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is False

    def test_iso8601_datetime_passes(self, create_context):
        """ISO 8601 のタイムゾーン付き日時表記はパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日時"],
                    ["太郎", "2026-05-13T15:30:30+09:00"],
                    ["花子", "2026-05-14T09:00:00+09:00"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_iso8601_date_only_passes(self, create_context):
        """ISO 8601 の日付のみ表記（YYYY-MM-DD）はパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日付"],
                    ["太郎", "2026-05-13"],
                    ["花子", "2026-05-14"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_jis_x0301_wareki_passes(self, create_context):
        """JIS X 0301 の和暦短縮表現（R8.05.13）はパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日付"],
                    ["太郎", "R8.05.13"],
                    ["花子", "R8.05.14"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_jis_x0301_extended_datetime_passes(self, create_context):
        """JIS X 0301 の西暦拡張表現（タイムゾーンなし）はパス"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日時"],
                    ["太郎", "2026-05-13T15:30:30"],
                    ["花子", "2026-05-14T09:00:00"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_iso8601_and_jis_wareki_mix_detected(self, create_context):
        """許可フォーマット同士（ISO 8601 / JIS X 0301 和暦短縮）でも同一列内の混在は違反"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日付"],
                    ["太郎", "2026-05-13T15:30:30+09:00"],
                    ["花子", "R8.05.14"],
                    ["次郎", "2026-05-15"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("混在" in v.description for v in result.violations)

    def test_estat_and_iso8601_mix_detected(self, create_context):
        """e-Stat 漢字区切りと ISO 8601 日付の混在も違反として検出"""
        ctx = create_context(
            {
                "Sheet1": [
                    ["名前", "日付"],
                    ["太郎", "2023年4月"],
                    ["花子", "2023-05-13"],
                ],
            },
        )
        rule = TimeAxisStandardizationRule()
        result = rule.check(ctx)
        assert result.passed is False
        assert any("混在" in v.description for v in result.violations)
