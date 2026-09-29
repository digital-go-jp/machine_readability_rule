"""AI利用メトリクス追跡モジュール

AI API呼び出しの回数・処理時間・トークン数・推定コストを記録する。
スレッドセーフなシングルトン。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class AICallRecord:
    """1回のAI API呼び出しの記録。"""

    method: str
    model: str
    duration_sec: float
    input_tokens: int
    output_tokens: int
    success: bool


@dataclass
class AIMetricsSummary:
    """メトリクスの集計結果。"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_sec: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    calls: list[AICallRecord] = field(default_factory=list)


# 主要モデルの概算料金（USD / 1M tokens）
_PRICING: dict[str, dict[str, float]] = {
    # Gemini
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    # Anthropic
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-20250414": {"input": 0.80, "output": 4.0},
}

# モデル名に "/"プレフィクスが付いている場合（LiteLLM形式）の検索用
_DEFAULT_PRICING = {"input": 2.50, "output": 10.0}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """推定コスト（USD）を計算する。"""
    # "gemini/gemini-2.5-pro" → "gemini-2.5-pro" のように "/" 以降で検索
    model_key = model.split("/")[-1] if "/" in model else model
    pricing = _PRICING.get(model_key, _DEFAULT_PRICING)
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


class AIMetricsTracker:
    """AI API呼び出しのメトリクスを追跡するスレッドセーフなトラッカー。"""

    _instance: AIMetricsTracker | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AIMetricsTracker:
        """シングルトンインスタンスを返す（未生成ならスレッドセーフに生成）。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """メトリクスをリセットする。"""
        with cls._lock:
            cls._instance = cls()

    def __init__(self) -> None:
        self._records: list[AICallRecord] = []
        self._lock_records = threading.Lock()

    def record_call(
        self,
        *,
        method: str,
        model: str,
        duration_sec: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
    ) -> None:
        """API呼び出しを記録する。"""
        record = AICallRecord(
            method=method,
            model=model,
            duration_sec=duration_sec,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
        )
        with self._lock_records:
            self._records.append(record)

    def get_summary(self) -> AIMetricsSummary:
        """現在のメトリクスの集計を返す。"""
        with self._lock_records:
            records = list(self._records)

        summary = AIMetricsSummary(calls=records)
        for r in records:
            summary.total_calls += 1
            if r.success:
                summary.successful_calls += 1
            else:
                summary.failed_calls += 1
            summary.total_duration_sec += r.duration_sec
            summary.total_input_tokens += r.input_tokens
            summary.total_output_tokens += r.output_tokens
            summary.estimated_cost_usd += _estimate_cost(r.model, r.input_tokens, r.output_tokens)
        return summary


class track_ai_call:  # noqa: N801
    """AI API呼び出しの計測用コンテキストマネージャー。

    使用例::

        with track_ai_call("batch_infer_units", "gemini-2.5-pro") as tracker:
            response = client.generate(...)
            tracker.set_tokens(response)
    """

    def __init__(self, method: str, model: str) -> None:
        self.method = method
        self.model = model
        self._start: float = 0.0
        self._input_tokens = 0
        self._output_tokens = 0
        self._success = True

    def __enter__(self) -> track_ai_call:
        """計測を開始し（開始時刻を記録）、自身を返す。"""
        self._start = time.monotonic()
        return self

    def set_tokens_from_response(self, response) -> None:
        """レスポンスからトークン数を抽出する（Gemini / LiteLLM 両対応）。"""
        try:
            # LiteLLM / OpenAI 形式: response.usage.prompt_tokens
            if hasattr(response, "usage") and hasattr(response.usage, "prompt_tokens"):
                self._input_tokens = response.usage.prompt_tokens or 0
                self._output_tokens = response.usage.completion_tokens or 0
            # Gemini 形式: response.usage_metadata.prompt_token_count
            elif hasattr(response, "usage_metadata"):
                usage = response.usage_metadata
                if usage:
                    self._input_tokens = getattr(usage, "prompt_token_count", 0) or 0
                    self._output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        except Exception:
            pass

    def set_failed(self) -> None:
        """この呼び出しを失敗として記録するようマークする。"""
        self._success = False

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """経過時間を計測し、成否・トークン数を含めて呼び出し記録を確定する。"""
        duration = time.monotonic() - self._start
        if exc_type is not None:
            self._success = False
        AIMetricsTracker.get_instance().record_call(
            method=self.method,
            model=self.model,
            duration_sec=duration,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            success=self._success,
        )
        return None
