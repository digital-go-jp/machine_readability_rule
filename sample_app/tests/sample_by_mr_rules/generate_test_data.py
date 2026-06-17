# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "openpyxl>=3.1.0",
#   "python-docx>=1.1.2",
#   "reportlab>=4.4.0",
#   "pillow>=10.0.0",
#   "xlsxwriter>=3.1.0",
# ]
# ///
"""登録済みルール別のサンプルデータを生成する（RULE_GENERATORS_BY_NUMBER のキー）。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from sample_generators import RULE_GENERATORS_BY_NUMBER

OUTPUT_DIR = Path(__file__).resolve().parent / "samples"


def rule_output_prefix(rule_number: int) -> str:
    return f"rule_{rule_number:02d}_"


def cleanup_previous_outputs(*, rule_numbers: list[int]) -> None:
    """指定ルールに対応する samples 内の既存ファイルのみ削除する。"""
    prefixes = [rule_output_prefix(n) for n in rule_numbers]
    if not OUTPUT_DIR.exists():
        return

    for path in OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        if any(path.name.startswith(prefix) for prefix in prefixes):
            path.unlink()


def parse_rule_numbers_arg(rules_arg: str | None) -> list[int] | None:
    """--rules の文字列を番号リストにする。None は「全ルール」。"""
    if rules_arg is None or not rules_arg.strip():
        return None
    parts = [p for p in re.split(r"[\s,]+", rules_arg.strip()) if p]
    if not parts:
        return None
    return [int(p) for p in parts]


def resolve_rule_numbers(rules_arg: str | None) -> list[int]:
    """検証済みのルール番号リスト（昇順・重複除去）。"""
    parsed = parse_rule_numbers_arg(rules_arg)
    if parsed is None:
        return sorted(RULE_GENERATORS_BY_NUMBER)

    valid = set(RULE_GENERATORS_BY_NUMBER)
    unknown = [n for n in parsed if n not in valid]
    if unknown:
        raise SystemExit(
            f"無効なルール番号です: {unknown}。利用可能: {sorted(valid)}",
        )
    return sorted(set(parsed))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="機械可読性ルール別のサンプルデータを生成する。",
    )
    parser.add_argument(
        "--rules",
        "-r",
        metavar="N",
        help=(
            "生成するルール番号（RULE_GENERATORS_BY_NUMBER に登録された番号）。"
            "カンマ区切りまたは空白区切りで複数指定可。"
            "例: --rules 10  または  -r 8,10 。省略時は全ルールを生成する。"
        ),
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    rule_numbers = resolve_rule_numbers(args.rules)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_previous_outputs(rule_numbers=rule_numbers)

    generators = [(n, RULE_GENERATORS_BY_NUMBER[n]) for n in rule_numbers]
    generated_paths: list[Path] = []
    for rule_no, generate in generators:
        artifacts = generate(OUTPUT_DIR)
        generated_paths.extend(artifacts)
        for path in artifacts:
            print(f"generated: {path.relative_to(OUTPUT_DIR.parent)} (rule {rule_no})")

    print(f"\n合計: {len(generators)} ルール分のテストデータを生成")
    print(f"出力先: {OUTPUT_DIR}")
    print(f"生成ファイル数: {len(generated_paths)}")


if __name__ == "__main__":
    main()
