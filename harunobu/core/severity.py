"""ルール失敗の重大度（Severity）

スコアリング・ポリシーで「強制 0 点」のトリガーおよび固定減点計算に用いる。
ルール側はクラス属性 ``severity`` で宣言し、Scorer が読み取る。

スコア算出ルール:

- FATAL 失敗 → そのレベルは強制 0 点（``FORCED_ZERO_SEVERITIES``）
- それ以外の失敗 → ``SEVERITY_DEDUCTIONS[(severity, level)]`` の固定点数を減点
- ``score = max(0, 100 − 減点合計)``

Note:
    ``Violation.severity``（error/warning/info）は「セル単位の重大度」であり、
    本 Severity（ルール失敗の重大度）とは独立した概念として共存する。
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """ルール失敗の重大度。

    順序（厳しい順）: FATAL > CRITICAL > MAJOR > MINOR > INFO

    Scorer のデフォルトポリシーでは FATAL のみが強制 0 点をトリガーする。
    CRITICAL/MAJOR/MINOR は ``SEVERITY_DEDUCTIONS`` の固定減点でスコアに影響する。
    用途に応じて ``LevelScorer(forced_zero_severities=...)`` で差し替え可能。
    """

    FATAL = "fatal"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


FORCED_ZERO_SEVERITIES: frozenset[Severity] = frozenset({Severity.FATAL})
"""失敗時にそのレベルを強制 0 点にする severity 集合（デフォルトは FATAL のみ）。"""

SEVERITY_DEDUCTIONS: dict[tuple[Severity, int], int] = {
    # (severity, level): 固定減点
    # FATAL は強制ゼロ点専用のため含まない。
    # FATAL ルールおよびConfidence=0による判定対象外ルール以外の全てが失敗した場合の最大減点:
    #   Level 1 (CRITICAL×9 + MAJOR×1 + MINOR×1): 97 点 → 最低 3 点
    #   Level 2 (CRITICAL×1 + MAJOR×2):           100 点 → 最低 0 点
    #   Level 3 (CRITICAL×3 + MAJOR×5):            95 点 → 最低 5 点
    (Severity.CRITICAL, 1): 10,
    (Severity.MAJOR, 1): 5,
    (Severity.MINOR, 1): 2,
    (Severity.INFO, 1): 0,
    (Severity.CRITICAL, 2): 40,
    (Severity.MAJOR, 2): 30,
    (Severity.MINOR, 2): 10,
    (Severity.INFO, 2): 0,
    (Severity.CRITICAL, 3): 15,
    (Severity.MAJOR, 3): 10,
    (Severity.MINOR, 3): 5,
    (Severity.INFO, 3): 0,
}
"""severity × level の組み合わせごとの固定減点。
FATAL は ``FORCED_ZERO_SEVERITIES`` で別途管理するためこのテーブルに含まない。"""
