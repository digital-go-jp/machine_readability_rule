"""AIセマンティックチェッカー - LLM を使ったセマンティック検証

決定論的ルールでは検出できない意味的な問題を AI で補完する。
AI が利用できない場合は graceful fallback する（既存の確信度を下げて返す）。
LiteLLM 経由で Gemini / OpenAI / Anthropic 等の任意プロバイダーを利用可能。
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_ADMIN_DATA_CONTEXT = """あなたは日本の行政データを分析するエキスパートです。
対象データは以下のような行政機関のExcelファイルです:
- こども家庭庁（保育所・福祉データ）
- 厚生労働省（医療・介護・雇用データ）
- 文部科学省（教育データ）
- 総務省（地方財政・水道事業データ）

行政データ特有の表現:
- 秘匿値: 「-」「×」「…」「＊」「－」（個人情報保護上の非公開）
- 単位省略: 「（百万円）」をヘッダーに記載し数値列は単位なし
- 年度表記: 「令和5年度」「R5」「2023年度」が混在することがある
- 地域コード: JIS X 0401/0402 準拠の都道府県・市区町村コード
- 「0」始まりコード: 都道府県コード「01」等は文字列として保持すべき
"""


class AISemanticChecker:
    """LLM を使ったセマンティックチェック。

    シングルトンパターン。AI が利用できない場合は graceful fallback する。
    AIClient 経由で任意のプロバイダー（Gemini / OpenAI / Anthropic 等）を利用可能。
    """

    _instance: AISemanticChecker | None = None

    @classmethod
    def get_instance(cls) -> AISemanticChecker:
        """シングルトンインスタンスを返す。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """テスト用: インスタンスをリセットする。"""
        cls._instance = None

    def __init__(self) -> None:
        self._available: bool | None = None

    def is_available(self) -> bool:
        """AI が利用可能かチェックする。"""
        if os.environ.get("HARUNOBU_AI_DISABLED", "").lower() in ("1", "true", "yes"):
            return False
        if self._available is not None:
            return self._available
        try:
            from harunobu.core.ai_client import AIClient

            self._available = AIClient.get_instance().is_available()
        except Exception as e:
            self._available = False
            logger.debug("AI checker not available: %s", e)
        return self._available

    def _generate_json(self, prompt: str, *, method_name: str = "unknown") -> Any | None:
        """AI を呼び出して JSON を生成する。エラー時は None を返す。"""
        if not self.is_available():
            return None
        from harunobu.core.ai_client import AIClient

        return AIClient.get_instance().generate_json(prompt, method_name=method_name)

    # ─── セマンティックチェック API ─────────────────────────────────────────

    # ─── バッチ API ─────────────────────────────────────────────────────

    def batch_check_zero_unlikely_columns(
        self,
        items: list[tuple[str, list]],  # [(header, sample_values), ...]
    ) -> list[dict] | None:
        """複数列のヘッダー意味から「ゼロが発生しにくい列か」を一括判定する。

        Returns:
            list[dict] | None: 各列に対応する ``{zero_unlikely, reason, confidence}`` のリスト。
                AI が利用不可・items 空の場合はデフォルト値リスト。
                API 呼び出し失敗時は ``None``（呼び出し元で confidence=0 に落とすこと）。
        """
        default = {"zero_unlikely": False, "reason": "", "confidence": 0.0}
        if not self.is_available() or not items:
            return [default for _ in items]

        columns_text = "\n".join(
            f"  [{i}] ヘッダー: 「{header}」, サンプル値: {', '.join(str(v) for v in samples[:10])}"
            for i, (header, samples) in enumerate(items)
        )

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下の各列について、値として「0（ゼロ）」が自然に発生しにくい列かどうかを判断してください。
列には空白セルとゼロ値が混在しており、ゼロが不自然であれば空白が「データなし」の誤記である可能性があります。

{columns_text}

ゼロが発生しにくい列の例（zero_unlikely=true）:
- 「人口」「世帯数」「定員数」など — カウント系、集落・施設が存在する以上ゼロは非現実的
- 「面積」「延床面積」など — 面積がゼロの施設・地域は原則存在しない
- 「標準人員」「職員数」など — 存在する機関の職員がゼロは通常ない

ゼロが正常に発生する列の例（zero_unlikely=false）:
- 「変化率」「増減数」「前年比」など — ゼロ成長・ゼロ変化は正常値
- 「補助金額」「交付金」など — 未交付（ゼロ）は通常の状態
- 「不合格者数」「欠員数」「空き定員」など — ゼロは正常値
- 「件数」「回数」など — 発生なしのゼロは正常

JSON回答（インデックス順の配列）:
[{{"zero_unlikely": true/false, "reason": "判断理由", "confidence": 0.0から1.0}}]"""

        result = self._generate_json(prompt, method_name="batch_check_zero_unlikely_columns")
        if result is None or not isinstance(result, list):
            return None

        out = []
        for i in range(len(items)):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "zero_unlikely": bool(result[i].get("zero_unlikely", False)),
                        "reason": str(result[i].get("reason", "")),
                        "confidence": float(result[i].get("confidence", 0.0)),
                    }
                )
            else:
                out.append(default)
        return out

    def batch_infer_units_from_headers(
        self,
        items: list[tuple[str, list]],  # [(header, sample_values), ...]
    ) -> list[dict]:
        """複数列のヘッダーから単位を一括推測する。1回の API 呼出で処理。

        Returns:
            list[dict]: 各列に対応する ``{has_unit, inferred_unit, explanation}`` のリスト。
        """
        empty = {"has_unit": False, "inferred_unit": None, "explanation": ""}
        if not self.is_available() or not items:
            return [empty for _ in items]

        columns_text = "\n".join(
            f"  [{i}] ヘッダー: 「{header}」, サンプル値: {', '.join(str(v) for v in samples[:5])}"
            for i, (header, samples) in enumerate(items)
        )

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下の複数の列について、それぞれヘッダーからデータ単位が明記・推定可能か判断してください。

{columns_text}

判断基準:
- ヘッダーに「（円）」「（人）」などの単位が括弧内に記載 → 単位あり
- ヘッダー名自体が単位を暗示: 「人口」→人, 「金額」→円, 「受診率」→%, 「面積」→㎡
- ヘッダーが「A」「B」など単位が推定不可能 → 単位なし

JSON回答（インデックス順の配列）:
[{{"has_unit": true/false, "inferred_unit": "推定単位またはnull", "explanation": "判断理由"}}]"""

        result = self._generate_json(prompt, method_name="batch_infer_units_from_headers")
        if result is None or not isinstance(result, list):
            return [empty for _ in items]

        # 結果数が足りない場合はデフォルトで埋める
        out = []
        for i in range(len(items)):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "has_unit": bool(result[i].get("has_unit", False)),
                        "inferred_unit": result[i].get("inferred_unit"),
                        "explanation": str(result[i].get("explanation", "")),
                    }
                )
            else:
                out.append(empty)
        return out

    def batch_check_code_needs_table(
        self,
        items: list[tuple[str, list]],  # [(header, sample_values), ...]
    ) -> list[dict]:
        """複数列がコード値を含みコード表が必要かを一括判定する。

        Returns:
            list[dict]: 各列に対応する ``{needs_code_table, code_type, explanation}`` のリスト。
        """
        empty = {"needs_code_table": False, "code_type": "", "explanation": ""}
        if not self.is_available() or not items:
            return [empty for _ in items]

        columns_text = "\n".join(
            f"  [{i}] ヘッダー: 「{header}」, 値: {', '.join(str(v) for v in samples[:10])}"
            for i, (header, samples) in enumerate(items)
        )

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下の複数の列について、それぞれコード値を含んでいてコード表が必要か判断してください。

{columns_text}

コード表が必要な例: 性別コード（1=男,2=女）, 市区町村コード, 産業分類コード
コード表が不要な例: 人数・件数, 年度, 順位, 都道府県名

JSON回答（インデックス順の配列）:
[{{"needs_code_table": true/false, "code_type": "コードの種類", "explanation": "判断理由"}}]"""

        result = self._generate_json(prompt, method_name="batch_check_code_needs_table")
        if result is None or not isinstance(result, list):
            return [empty for _ in items]

        out = []
        for i in range(len(items)):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "needs_code_table": bool(result[i].get("needs_code_table", False)),
                        "code_type": str(result[i].get("code_type", "")),
                        "explanation": str(result[i].get("explanation", "")),
                    }
                )
            else:
                out.append(empty)
        return out

    def batch_check_special_symbol_intents(
        self,
        items: list[tuple[str, str, list[str]]],  # [(symbol, column_header, column_values), ...]
    ) -> list[dict]:
        """複数の特殊記号の意図を一括判定する。

        Returns:
            list[dict]: 各記号に対応する ``{is_statistical_marker, likely_meaning, confidence}`` のリスト。
        """
        default = {"is_statistical_marker": True, "likely_meaning": "不明", "confidence": 0.5}
        if not self.is_available() or not items:
            return [default for _ in items]

        def _numeric_ratio(vals: list[str]) -> str:
            n = sum(1 for v in vals if v.replace(",", "").replace(".", "").lstrip("-").strip().isdigit())
            return f"{n / max(len(vals), 1):.0%}"

        symbols_text = "\n".join(
            f"  [{i}] 記号: '{symbol}', 列名: 「{header}」, "
            f"数値割合: {_numeric_ratio(vals)}, "
            f"サンプル値: {', '.join(repr(v) for v in vals[:15])}"
            for i, (symbol, header, vals) in enumerate(items)
        )

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下の複数の記号について、それぞれ統計データの特殊マーカーか通常データか判断してください。

{symbols_text}

A) 統計マーカー（欠損値・秘匿・不詳・該当なし等）
B) 通常データ（負の数を示す '-'、テキストの一部等）

JSON回答（インデックス順の配列）:
[{{"is_statistical_marker": true/false, "likely_meaning": "推定意味", "confidence": 0.0から1.0}}]"""

        result = self._generate_json(prompt, method_name="batch_check_special_symbol_intents")
        if result is None or not isinstance(result, list):
            return [default for _ in items]

        out = []
        for i in range(len(items)):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "is_statistical_marker": bool(result[i].get("is_statistical_marker", True)),
                        "likely_meaning": str(result[i].get("likely_meaning", "不明")),
                        "confidence": float(result[i].get("confidence", 0.5)),
                    }
                )
            else:
                out.append(default)
        return out

    def batch_check_unit_in_cells(
        self,
        items: list[tuple[str, str]],  # [(cell_value, column_header), ...]
    ) -> list[dict]:
        """複数セルの単位混在を一括検出する。

        Returns:
            list[dict]: 各セルに対応する ``{has_unit, numeric_part, unit_part, confidence}`` のリスト。
        """
        empty = {"has_unit": False, "numeric_part": "", "unit_part": "", "confidence": 0.0}
        if not self.is_available() or not items:
            return [{**empty, "numeric_part": v} for v, _ in items] if items else []

        cells_text = "\n".join(f"  [{i}] 列「{header}」: 「{value}」" for i, (value, header) in enumerate(items))

        prompt = f"""以下の複数のセル値について、数値と単位が混在していないか分析してください。

{cells_text}

行政データの単位混在パターン:
- 「約1,200名」→ 数値="1200", 単位="名"
- 「500千円」→ 数値="500", 単位="千円"
- 「3.5%」→ 数値="3.5", 単位="%"
- 「1,234」→ 数値="1234", 単位=""（純粋な数値）

JSON回答（インデックス順の配列）:
[{{"has_unit": true/false, "numeric_part": "数値部分", "unit_part": "単位部分", "confidence": 0.0から1.0}}]"""

        result = self._generate_json(prompt, method_name="batch_check_unit_in_cells")
        if result is None or not isinstance(result, list):
            return [{**empty, "numeric_part": v} for v, _ in items]

        out = []
        for i, (value, _header) in enumerate(items):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "has_unit": bool(result[i].get("has_unit", False)),
                        "numeric_part": str(result[i].get("numeric_part", value)),
                        "unit_part": str(result[i].get("unit_part", "")),
                        "confidence": float(result[i].get("confidence", 0.5)),
                    }
                )
            else:
                out.append({**empty, "numeric_part": value})
        return out

    def batch_check_other_detail_mixed(
        self,
        items: list[tuple[str, str]],  # [(cell_value, column_header), ...]
    ) -> list[dict]:
        """複数セルの「その他（detail）」混在パターンを一括検出する。

        Returns:
            list[dict]: 各セルに対応する ``{is_mixed, other_part, detail_part, confidence}`` のリスト。
        """
        empty = {"is_mixed": False, "other_part": "", "detail_part": "", "confidence": 0.0}
        if not self.is_available() or not items:
            return [empty for _ in items]

        cells_text = "\n".join(f"  [{i}] 列「{header}」: 「{value}」" for i, (value, header) in enumerate(items))

        prompt = f"""以下の複数のセル値について、「その他」と詳細情報の混在パターンか判定してください。

{cells_text}

混在パターンの例: 「その他_駐車場利用」「その他（施設管理）」
混在でない例: 「その他」（単独）、「その他の経費」（自然な列名）

JSON回答（インデックス順の配列）:
[{{"is_mixed": true/false, "other_part": "その他部分", "detail_part": "詳細部分", "confidence": 0.0から1.0}}]"""

        result = self._generate_json(prompt, method_name="batch_check_other_detail_mixed")
        if result is None or not isinstance(result, list):
            return [empty for _ in items]

        out = []
        for i in range(len(items)):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "is_mixed": bool(result[i].get("is_mixed", False)),
                        "other_part": str(result[i].get("other_part", "")),
                        "detail_part": str(result[i].get("detail_part", "")),
                        "confidence": float(result[i].get("confidence", 0.5)),
                    }
                )
            else:
                out.append(empty)
        return out

    def batch_normalize_time_values(
        self,
        items: list[tuple[str, str]],  # [(value, context_column), ...]
    ) -> list[dict]:
        """複数の時間軸値を一括で正規化する。

        Returns:
            list[dict]: 各値に対応する ``{normalized, original_era, confidence}`` のリスト。
        """
        empty = {"normalized": "", "original_era": "", "confidence": 0.0}
        if not self.is_available() or not items:
            return [empty for _ in items]

        values_text = "\n".join(f"  [{i}] 列「{col}」: 「{val}」" for i, (val, col) in enumerate(items))

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下の複数の時間軸の値を西暦の標準形式に正規化してください。

{values_text}

和暦の換算: 明治+1867, 大正+1911, 昭和+1925, 平成+1988, 令和+2018
正規化できない場合は normalized="" としてください。

JSON回答（インデックス順の配列）:
[{{"normalized": "正規化後の値", "original_era": "元号", "confidence": 0.0から1.0}}]"""

        result = self._generate_json(prompt, method_name="batch_normalize_time_values")
        if result is None or not isinstance(result, list):
            return [empty for _ in items]

        out = []
        for i in range(len(items)):
            if i < len(result) and isinstance(result[i], dict):
                out.append(
                    {
                        "normalized": str(result[i].get("normalized", "")),
                        "original_era": str(result[i].get("original_era", "")),
                        "confidence": float(result[i].get("confidence", 0.5)),
                    }
                )
            else:
                out.append(empty)
        return out

    # ─── セマンティックチェック API ─────────────────────────────────────────

    def check_abbreviations(
        self,
        column_data: list[tuple[int, int, str]],  # (row, col, value)
        header: str,
        sheet_name: str = "",
    ) -> list[dict]:
        """列の省略（繰り返し省略・略称）を AI で検出する。

        Returns:
            list[dict]: 省略の疑いがあるセルの ``{row, col, value, reason}`` 辞書のリスト。
        """
        if not self.is_available() or not column_data:
            return []

        sample = column_data[:50]
        rows_text = "\n".join(f"  行{row}: {repr(value)}" for row, col, value in sample)

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下は「{header}」という列のデータです（シート: {sheet_name}）。
各行の値が省略（前の行の値の繰り返し省略・略称・省略記号）になっていないか分析してください。

データ:
{rows_text}

省略と判断できる行をJSONで返してください。省略でない場合は空のリストを返してください。
判断に迷う場合は省略とみなさないでください（誤検出より見逃しを優先）。

省略の例:
- 空白セルが連続（前の値の繰り返しとして空白を使用）
- 「同」「同上」「〃」などの省略記号
- ヘッダーが「年度」でデータが「H28」「H29」などの和暦略称

FP回避:
- 同じ値が連続しても、それが正しいデータであれば省略ではない（例: 同一市町村名の繰り返し）
- 空白セルが連続していても、そのセルに値がないことが正常なケースもある

レスポンス: [{{"row": 数値, "value": "文字列", "reason": "省略の理由"}}]
省略なし: []"""

        result = self._generate_json(prompt, method_name="check_abbreviations")
        if result is None or not isinstance(result, list):
            return []

        row_to_col = {r: c for r, c, v in column_data}
        violations = []
        for item in result:
            if not isinstance(item, dict):
                continue
            row = item.get("row")
            value = item.get("value", "")
            reason = item.get("reason", "AIによる省略検出")
            if row is not None and row in row_to_col:
                violations.append({"row": row, "col": row_to_col[row], "value": value, "reason": reason})
        return violations

    def check_wide_format_semantic(
        self,
        headers: list[str],
        sample_rows: list[list[str]] | None = None,
    ) -> dict:
        """ヘッダーが非時間軸カテゴリの横持ち形式かを AI で検出する。

        Returns:
            dict: ``{is_wide: bool, category_type: str, details: str, confidence: float}``
        """
        if not self.is_available() or not headers:
            return {"is_wide": False, "category_type": "", "details": "", "confidence": 0.0}

        header_sample = headers[:30]
        headers_text = ", ".join(f"'{h}'" for h in header_sample)

        sample_text = ""
        if sample_rows:
            sample_text = "\n最初の3行のデータ:\n"
            for row in sample_rows[:3]:
                sample_text += "  " + " | ".join(str(v) for v in row[: len(header_sample)]) + "\n"

        prompt = f"""{_ADMIN_DATA_CONTEXT}
以下はスプレッドシートのヘッダー行の値です:
{headers_text}{sample_text}

これらのヘッダーが「カテゴリ値として横持ち（ワイド形式）」になっていないか判断してください。

横持ちの例（これらを検出してください）:
- 47都道府県名（北海道, 青森県, 岩手県, ...）が列名になっている
- 性別（男性, 女性, 不明）が列名になっている
- 年齢区分（0-4歳, 5-9歳, ...）が列名になっている
- 産業分類が列名になっている
- 学校種別や施設種別が列名になっている

※ 年・月・期などの時間軸は別ルールでチェック済みのため除外してください。
※ 通常の項目名（名称, 人口, 面積など）は横持ちではありません。

JSON回答:
{{"is_wide": true/false, "category_type": "カテゴリの種類（例: 都道府県, 性別）",
"details": "詳細説明", "confidence": 0.0から1.0}}"""

        result = self._generate_json(prompt, method_name="check_wide_format_semantic")
        if result is None or not isinstance(result, dict):
            return {"is_wide": False, "category_type": "", "details": "", "confidence": 0.0}

        return {
            "is_wide": bool(result.get("is_wide", False)),
            "category_type": str(result.get("category_type", "")),
            "details": str(result.get("details", "")),
            "confidence": float(result.get("confidence", 0.5)),
        }

    def check_special_symbol_intent(
        self,
        symbol: str,
        column_header: str,
        column_values: list[str],
    ) -> dict:
        """特殊記号の意図（統計マーカー vs 通常データ）を AI で判定する。

        Returns:
            dict: ``{is_statistical_marker: bool, likely_meaning: str, confidence: float}``
        """
        if not self.is_available():
            return {"is_statistical_marker": True, "likely_meaning": "不明", "confidence": 0.5}

        numeric_count = sum(
            1 for v in column_values if v.replace(",", "").replace(".", "").lstrip("-").strip().isdigit()
        )
        total = len(column_values)
        numeric_ratio = numeric_count / total if total > 0 else 0

        sample = column_values[:20]
        values_text = ", ".join(f"'{v}'" for v in sample)

        prompt = f"""{_ADMIN_DATA_CONTEXT}
スプレッドシートの「{column_header}」列に記号 '{symbol}' が含まれています。
列のサンプル値: {values_text}
列の数値割合: {numeric_ratio:.0%}

この '{symbol}' は:
A) 統計データの特殊マーカー（欠損値・秘匿・不詳・該当なしなど）
B) 通常のデータ（負の数を示す '-'、テキストの一部など）

どちらとして使われているか判断してください。

実例（FP回避パターン）:
- 「-」が列「経常収支比率(%)」にある → 数値列の「-」は秘匿値（統計マーカー）
- 「-」が列「備考」にある → テキスト列の「-」は通常の区切り（統計マーカーではない）
- 「×」が列「保育所定員」にある → 秘匿値（統計マーカー）
- 「0」が列「件数」にある → 通常の数値（統計マーカーではない）

JSON回答:
{{"is_statistical_marker": true/false,
"likely_meaning": "推定意味（例: 該当なし, 秘匿, 負の値）", "confidence": 0.0から1.0}}"""

        result = self._generate_json(prompt, method_name="check_special_symbol_intent")
        if result is None or not isinstance(result, dict):
            return {"is_statistical_marker": True, "likely_meaning": "不明", "confidence": 0.5}

        return {
            "is_statistical_marker": bool(result.get("is_statistical_marker", True)),
            "likely_meaning": str(result.get("likely_meaning", "不明")),
            "confidence": float(result.get("confidence", 0.5)),
        }

    def check_choice_variants(
        self,
        column_values: list[str],
        header: str,
    ) -> list[list[str]]:
        """意味的に同じだが表記が異なる選択肢グループを AI で検出する。

        Returns:
            list[list[str]]: 意味的に等価な値を1つにまとめたグループのリスト。
        """
        if not self.is_available() or not column_values:
            return []

        unique_values = list(dict.fromkeys(v for v in column_values if v.strip()))
        if len(unique_values) < 2 or len(unique_values) > 50:
            return []

        values_text = ", ".join(f"'{v}'" for v in unique_values)

        prompt = f"""{_ADMIN_DATA_CONTEXT}
列「{header}」のユニーク値一覧:
{values_text}

これらの値の中で、意味は同じだが表記が異なるグループを見つけてください。

例:
- ["男性", "男", "M", "male"] → 同じ意味
- ["有", "あり", "○", "Yes", "YES"] → 同じ意味
- ["受けた", "受診した", "済"] → 同じ意味
- ["要支援1", "要支援１"] → 全角半角の違いで同じ意味

行政データの典型的な表記揺れ:
- 「有」「あり」「○」「1」→ 同じ意味で使われることがある
- 「受けた」「受診した」「済」→ 選択肢の表記が統一されていない
- 「要支援1」「要支援１」→ 全角/半角の違い
- 「男」「男性」「M」→ 性別の表記揺れ

表記揺れがあるグループのみ返してください（単独の値は含めない）。
確信がない場合は含めないでください。

JSON回答（表記揺れグループ）:
[["値1", "値2"], ["値3", "値4"]]
揺れなし: []"""

        result = self._generate_json(prompt, method_name="check_choice_variants")
        if result is None or not isinstance(result, list):
            return []

        unique_set = set(unique_values)
        valid_groups = []
        for group in result:
            if isinstance(group, list) and len(group) >= 2:
                valid = [v for v in group if v in unique_set]
                if len(valid) >= 2:
                    valid_groups.append(valid)
        return valid_groups

    def infer_unit_from_header(
        self,
        header: str,
        sample_values: list[Any],
    ) -> dict:
        """ヘッダーから数値列の単位を AI で推測する。

        Returns:
            dict: ``{has_unit: bool, inferred_unit: str | None, explanation: str}``
        """
        if not self.is_available():
            return {"has_unit": False, "inferred_unit": None, "explanation": ""}

        sample_text = ", ".join(str(v) for v in sample_values[:5])

        prompt = f"""{_ADMIN_DATA_CONTEXT}
スプレッドシートの列「{header}」はデータ単位が明記・推定可能ですか？
サンプル値: {sample_text}

判断基準:
- ヘッダーに「（円）」「（人）」などの単位が括弧内に記載 → 単位あり
- ヘッダー名から単位が自明:
  - 「人口」「利用者数」→ 人
  - 「金額」「費用」「予算」→ 円
  - 「受診率」「普及率」「割合」→ %
  - 「面積」→ ㎡ or ha
  - 「飼養頭数」→ 頭
  - 「DI値」→ 指数（単位なし）
  - 「延べ床面積」→ ㎡
- ヘッダーが「A」「B」など単位が推定不可能 → 単位なし

JSON回答:
{{"has_unit": true/false, "inferred_unit": "推定単位またはnull", "explanation": "判断理由"}}"""

        result = self._generate_json(prompt, method_name="infer_unit_from_header")
        if result is None or not isinstance(result, dict):
            return {"has_unit": False, "inferred_unit": None, "explanation": ""}

        return {
            "has_unit": bool(result.get("has_unit", False)),
            "inferred_unit": result.get("inferred_unit"),
            "explanation": str(result.get("explanation", "")),
        }

    def check_code_needs_table(
        self,
        header: str,
        sample_values: list[Any],
    ) -> dict:
        """列がコード値を含みコード表が必要かを AI で判定する。

        Returns:
            dict: ``{needs_code_table: bool, code_type: str, explanation: str}``
        """
        if not self.is_available():
            return {"needs_code_table": False, "code_type": "", "explanation": ""}

        sample_text = ", ".join(str(v) for v in sample_values[:10])

        prompt = f"""{_ADMIN_DATA_CONTEXT}
スプレッドシートの列「{header}」の値: {sample_text}

この列はコード値を含んでいて、コードと意味の対応表（コード表）が別途必要ですか？

コード表が必要な例:
- 性別コード（1=男, 2=女）
- 産業分類コード（A=農業, B=林業...）
- 市区町村コード（131016=千代田区）
- 学校種別コード（1=小学校, 2=中学校）
- 福祉サービス区分コード

コード表が不要な例:
- 人数・件数（数値だがコードではない）
- 年度（2020, 2021...）
- 順位（1, 2, 3...）
- 都道府県名（コードでなく名称）

JSON回答:
{{"needs_code_table": true/false, "code_type": "コードの種類（例: 性別コード）", "explanation": "判断理由"}}"""

        result = self._generate_json(prompt, method_name="check_code_needs_table")
        if result is None or not isinstance(result, dict):
            return {"needs_code_table": False, "code_type": "", "explanation": ""}

        return {
            "needs_code_table": bool(result.get("needs_code_table", False)),
            "code_type": str(result.get("code_type", "")),
            "explanation": str(result.get("explanation", "")),
        }

    def check_unit_in_cell(
        self,
        cell_value: str,
        column_header: str,
    ) -> dict:
        """セル値に単位が混在していないかを AI で検出する。

        行政データでは数値セルに「約1,200名（前年比+2%）」のように単位や補足情報が
        混在するケースがある。これを検出して数値部分と単位部分を分離する。

        Returns:
            dict: ``{has_unit: bool, numeric_part: str, unit_part: str, confidence: float}``
        """
        if not self.is_available():
            return {"has_unit": False, "numeric_part": cell_value, "unit_part": "", "confidence": 0.0}

        prompt = f"""以下のセル値に数値と単位が混在していないか分析してください。

列ヘッダー: 「{column_header}」
セル値: 「{cell_value}」

行政データでは以下のような単位混在パターンがあります:
- 「約1,200名（前年比+2%）」→ 数値部分="1200", 単位部分="名"
- 「500千円」→ 数値部分="500", 単位部分="千円"
- 「3.5%」→ 数値部分="3.5", 単位部分="%"
- 「120人」→ 数値部分="120", 単位部分="人"
- 「▲10」→ 数値部分="-10", 単位部分=""（単位なし、符号のみ）
- 「1,234」→ 数値部分="1234", 単位部分=""（純粋な数値）

単位が含まれている場合は has_unit=true としてください。
秘匿値（「x」「*」「-」など）や純粋な文字列は has_unit=false としてください。

JSON回答:
{{"has_unit": true/false, "numeric_part": "数値部分", "unit_part": "単位部分", "confidence": 0.0から1.0}}"""

        result = self._generate_json(prompt, method_name="check_unit_in_cell")
        if result is None or not isinstance(result, dict):
            return {"has_unit": False, "numeric_part": cell_value, "unit_part": "", "confidence": 0.0}

        return {
            "has_unit": bool(result.get("has_unit", False)),
            "numeric_part": str(result.get("numeric_part", cell_value)),
            "unit_part": str(result.get("unit_part", "")),
            "confidence": float(result.get("confidence", 0.5)),
        }

    def check_other_detail_mixed(
        self,
        cell_value: str,
        column_header: str,
    ) -> dict:
        """「その他（detail）」のような混在パターンを AI で検出する。

        行政データでは「その他_駐車場利用」「その他（施設管理）」のように
        「その他」と具体的な内容が1セルに混在するケースがある。

        Returns:
            dict: ``{is_mixed: bool, other_part: str, detail_part: str, confidence: float}``
        """
        if not self.is_available():
            return {"is_mixed": False, "other_part": "", "detail_part": "", "confidence": 0.0}

        prompt = f"""以下のセル値が「その他」と詳細情報の混在パターンかを判定してください。

列ヘッダー: 「{column_header}」
セル値: 「{cell_value}」

混在パターンの例:
- 「その他_駐車場利用」→ その他部分="その他", 詳細部分="駐車場利用"
- 「その他（施設管理）」→ その他部分="その他", 詳細部分="施設管理"
- 「その他・雑費」→ その他部分="その他", 詳細部分="雑費"
- 「Other_parking」→ その他部分="Other", 詳細部分="parking"

混在でない例:
- 「その他」→ 単独なので混在でない
- 「駐車場利用」→ 「その他」を含まないので混在でない
- 「その他の経費」→ 文脈により列名として自然な場合は混在でない

JSON回答:
{{"is_mixed": true/false, "other_part": "その他部分", "detail_part": "詳細部分", "confidence": 0.0から1.0}}"""

        result = self._generate_json(prompt, method_name="check_other_detail_mixed")
        if result is None or not isinstance(result, dict):
            return {"is_mixed": False, "other_part": "", "detail_part": "", "confidence": 0.0}

        return {
            "is_mixed": bool(result.get("is_mixed", False)),
            "other_part": str(result.get("other_part", "")),
            "detail_part": str(result.get("detail_part", "")),
            "confidence": float(result.get("confidence", 0.5)),
        }

    def normalize_time_value(
        self,
        value: str,
        context_column: str,
    ) -> dict:
        """時間軸の値を正規化する提案を AI で生成する。

        和暦略称や非標準的な時間表記を西暦に正規化する。

        Returns:
            dict: ``{normalized: str, original_era: str, confidence: float}``
        """
        if not self.is_available():
            return {"normalized": "", "original_era": "", "confidence": 0.0}

        prompt = f"""以下の時間軸の値を西暦の標準形式に正規化してください。

列ヘッダー: 「{context_column}」
値: 「{value}」

正規化の例:
- 「H29」→ normalized="2017", original_era="平成"
- 「R3」→ normalized="2021", original_era="令和"
- 「S60」→ normalized="1985", original_era="昭和"
- 「平成29年度」→ normalized="2017", original_era="平成"
- 「令和3年」→ normalized="2021", original_era="令和"
- 「2020年度」→ normalized="2020", original_era=""
- 「2020Q1」→ normalized="2020-Q1", original_era=""
- 「4月」→ normalized="04", original_era=""

和暦の換算:
- 明治: 年+1867
- 大正: 年+1911
- 昭和: 年+1925
- 平成: 年+1988
- 令和: 年+2018

正規化できない場合は normalized="" としてください。

JSON回答:
{{"normalized": "正規化後の値", "original_era": "元号（和暦の場合）", "confidence": 0.0から1.0}}"""

        result = self._generate_json(prompt, method_name="normalize_time_value")
        if result is None or not isinstance(result, dict):
            return {"normalized": "", "original_era": "", "confidence": 0.0}

        return {
            "normalized": str(result.get("normalized", "")),
            "original_era": str(result.get("original_era", "")),
            "confidence": float(result.get("confidence", 0.5)),
        }

    def check_metadata_quality(
        self,
        table_headers: list[str],
        found_metadata_items: list[str],
    ) -> dict:
        """メタデータ記述の品質を AI で評価する。

        行政データのメタデータ（タイトル、出典、単位、定義等）の充実度を評価し、
        不足項目や改善提案を返す。

        Returns:
            dict: ``{quality_score: float, missing_items: list[str], suggestions: list[str]}``
        """
        if not self.is_available():
            return {"quality_score": 0.0, "missing_items": [], "suggestions": []}

        headers_text = ", ".join(f"'{h}'" for h in table_headers[:30])
        metadata_text = ", ".join(f"'{m}'" for m in found_metadata_items) if found_metadata_items else "なし"

        prompt = f"""行政データのメタデータ品質を評価してください。

テーブルのヘッダー: {headers_text}
検出されたメタデータ項目: {metadata_text}

行政データに必要なメタデータ:
- タイトル（データの名称）
- 出典（作成機関・調査名）
- 作成日・更新日
- 単位（数値列の単位）
- 対象期間（調査対象の期間）
- 対象地域（調査対象の地域）
- 用語の定義（専門用語の説明）
- 注記・凡例（秘匿記号の説明等）

品質スコアは 0.0（メタデータなし）〜 1.0（十分なメタデータ）で評価してください。
不足している重要なメタデータ項目をリストアップし、改善提案をしてください。

JSON回答:
{{"quality_score": 0.0から1.0, "missing_items": ["不足項目1", "不足項目2"],
"suggestions": ["改善提案1", "改善提案2"]}}"""

        result = self._generate_json(prompt, method_name="check_metadata_quality")
        if result is None or not isinstance(result, dict):
            return {"quality_score": 0.0, "missing_items": [], "suggestions": []}

        missing = result.get("missing_items", [])
        if not isinstance(missing, list):
            missing = []

        suggestions = result.get("suggestions", [])
        if not isinstance(suggestions, list):
            suggestions = []

        return {
            "quality_score": float(result.get("quality_score", 0.0)),
            "missing_items": [str(m) for m in missing],
            "suggestions": [str(s) for s in suggestions],
        }

    def assess_column_header_clarity(
        self,
        headers: list[str],
    ) -> list[dict]:
        """列ヘッダーの明確さを AI で評価する。

        曖昧なヘッダーを検出し、改善提案を返す。

        Returns:
            list[dict]: ``{header: str, is_ambiguous: bool, suggested_improvement: str, reason: str}`` のリスト。
        """
        if not self.is_available() or not headers:
            return []

        header_sample = headers[:30]
        headers_text = ", ".join(f"'{h}'" for h in header_sample)

        prompt = f"""以下の行政データのスプレッドシート列ヘッダーの明確さを評価してください。

ヘッダー: {headers_text}

曖昧なヘッダーの例:
- 「値」→ 何の値か不明。「人口（人）」「面積（ha）」など具体的に
- 「区分」→ 何の区分か不明。「性別区分」「年齢区分」など具体的に
- 「A」「B」「C」→ アルファベットだけでは意味不明
- 「データ1」「項目2」→ 番号だけでは意味不明
- 「備考」→ これは一般的に許容される
- 「合計」→ 何の合計か不明な場合は曖昧

明確なヘッダーの例:
- 「都道府県名」「人口（人）」「面積（km²）」→ 明確
- 「年度」「月」→ 明確
- 「番号」「No.」→ 用途による

曖昧と判断したヘッダーのみ返してください。明確なものは含めないでください。
確信がない場合は曖昧とみなさないでください（誤検出より見逃しを優先）。

JSON回答:
[{{"header": "ヘッダー名", "is_ambiguous": true, "suggested_improvement": "改善案",
"reason": "曖昧な理由"}}]
すべて明確: []"""

        result = self._generate_json(prompt, method_name="assess_column_header_clarity")
        if result is None or not isinstance(result, list):
            return []

        header_set = set(header_sample)
        valid_results = []
        for item in result:
            if not isinstance(item, dict):
                continue
            header = item.get("header", "")
            if header in header_set:
                valid_results.append(
                    {
                        "header": str(header),
                        "is_ambiguous": bool(item.get("is_ambiguous", True)),
                        "suggested_improvement": str(item.get("suggested_improvement", "")),
                        "reason": str(item.get("reason", "")),
                    }
                )
        return valid_results
