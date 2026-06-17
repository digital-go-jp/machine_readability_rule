"""Harunobu CLI エントリーポイント。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_analyze(args: argparse.Namespace) -> None:
    """ファイルを採点する。"""
    from harunobu.core.analyzer import analyze
    from harunobu.core.models import Config
    from harunobu.output.csv_writer import to_csv_string
    from harunobu.output.json_writer import to_json

    config = Config(mode=args.mode)
    result = analyze(Path(args.file), config)

    if args.output == "json":
        output = to_json(result)
    else:
        output = to_csv_string(result)

    if args.out_path:
        Path(args.out_path).write_text(output, encoding="utf-8")
        print(f"結果を {args.out_path} に保存しました")
    else:
        print(output)


def main() -> None:
    """CLI のエントリーポイント。引数を解析してサブコマンドを実行する。"""
    parser = argparse.ArgumentParser(
        prog="harunobu",
        description="Harunobu — Excel/CSV/TSVを機械可読性ルールで判定するCLI",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # analyze
    p_analyze = subparsers.add_parser(
        "analyze",
        help="ファイルを判定してJSONまたはCSVで出力する",
        description=("Excel/CSV/TSVファイルを読み込み、行政データの機械可読性ルールに基づく判定結果を出力します。"),
        epilog=(
            "例:\n"
            "  uv run harunobu analyze data.xlsx\n"
            "  uv run harunobu analyze data.csv --mode lite\n"
            "  uv run harunobu analyze data.xlsx --mode thorough --output csv\n"
            "  uv run harunobu analyze data.xlsx --out-path result.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_analyze.add_argument("file", help="対象ファイルパス (.xlsx/.csv/.tsv)")
    p_analyze.add_argument(
        "--mode",
        choices=["lite", "standard", "thorough"],
        default="standard",
        help="判定モード。lite=L1のみ、standard=L1-L2、thorough=L1-L3 (既定: standard)",
    )
    p_analyze.add_argument(
        "--output",
        choices=["json", "csv"],
        default="json",
        help="出力形式。json=詳細な階層構造、csv=表形式の一覧 (既定: json)",
    )
    p_analyze.add_argument(
        "--out-path",
        help="出力先ファイルパス。省略時は標準出力に表示する",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    commands = {
        "analyze": cmd_analyze,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
