"""L1-01: ファイル形式チェック — sample_by_mr_rules サンプルによる検証

サンプル:
  - rule_01_file_format_OK.xlsx   → xlsx なので pass
  - rule_01_file_format_NG-01.pdf → 非対応拡張子で読み込み拒否
  - rule_01_file_format_NG-02.docx → 非対応拡張子で読み込み拒否
  - rule_01_file_format_NG-03.xlsx → 拡張子偽装（実体はPDF）、reader の MIME 検証で拒否
"""

from __future__ import annotations

import pytest

from harunobu.core.reader import UnsupportedFormatError
from tests.integration.sample_rules.conftest import (
    analyze_file,
    collect_samples,
    get_rule_result,
    is_ok_sample,
)

RULE_NUMBER = 1
RULE_ID = "L1-01"


@pytest.fixture(scope="module")
def sample_files(samples_dir):
    """L1-01 用サンプルを収集する。"""
    files = collect_samples(RULE_NUMBER, samples_dir)
    if not files:
        pytest.skip(f"rule_{RULE_NUMBER:02d}_* のサンプルが見つかりません")
    return files


@pytest.fixture(scope="module")
def ok_files(sample_files):
    return [f for f in sample_files if is_ok_sample(f)]


@pytest.fixture(scope="module")
def ng_files(sample_files):
    return [f for f in sample_files if not is_ok_sample(f)]


class TestL1_01_OK:
    """OK サンプル: 許可された形式のファイルは L1-01 に合格する。"""

    def test_ok_samples_exist(self, ok_files):
        assert len(ok_files) > 0, "OKサンプルが1つ以上必要"

    def test_ok_files_pass(self, ok_files):
        for path in ok_files:
            result = analyze_file(path)
            rule_result = get_rule_result(result, RULE_ID)
            assert rule_result["found"], f"{path.name}: L1-01 の結果が見つかりません"
            assert rule_result["passed"], (
                f"{path.name}: OK サンプルなのに L1-01 に不合格 "
                f"(severity={rule_result['severity']}, violations={rule_result['violation_count']})"
            )


class TestL1_01_NG:
    """NG サンプル: 非対応形式・拡張子偽装ファイルは読み込み時に拒否される。

    - 非対応拡張子 (.pdf, .docx) → UnsupportedFormatError
    - 拡張子偽装 (.xlsx だが実体はPDF) → validate_file_mime で UnsupportedFormatError
    """

    def test_ng_samples_exist(self, ng_files):
        assert len(ng_files) > 0, "NGサンプルが1つ以上必要"

    def test_ng_files_rejected(self, ng_files):
        for path in ng_files:
            with pytest.raises(UnsupportedFormatError):
                analyze_file(path)
