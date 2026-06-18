"""統一AIクライアント — LiteLLM / google.genai 二重バックエンド

LiteLLM がインストールされていれば任意プロバイダー（OpenAI, Anthropic, Gemini 等）
を利用し、未インストール時は google.genai で Gemini のみ動作する。
シングルトンパターン。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)


def _strip_code_fence(text: str) -> str:
    """Markdown のコードフェンス（```json … ```）を除去する。

    一部モデル（Anthropic claude-4.x 等）は ``response_format=json_object`` 指定でも
    JSON をコードフェンスで囲んで返すため、`json.loads` の前に取り除く。

    Args:
        text: LLM が返した生テキスト。

    Returns:
        フェンスを除去したテキスト（フェンスが無ければ trim のみ）。
    """
    s = text.strip()
    if not s.startswith("```"):
        return s
    # 先頭フェンス行（```json 等）を除去
    newline = s.find("\n")
    s = s[newline + 1 :] if newline != -1 else s[3:]
    # 末尾フェンスを除去
    s = s.rstrip()
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()


def _parse_json_response(text: str | None) -> Any | None:
    """LLM のテキスト応答を JSON として解釈する（コードフェンス耐性あり）。

    Args:
        text: LLM が返した生テキスト。空・None の場合は None を返す。

    Returns:
        解析済みオブジェクト。本文が空の場合は None。
    """
    if not text:
        return None
    cleaned = _strip_code_fence(text)
    return json.loads(cleaned) if cleaned else None


def _resolve_ai_config() -> tuple[str, str, str | None]:
    """環境変数から (provider, model, fallback_model) を解決する。"""
    provider = os.environ.get("HARUNOBU_AI_PROVIDER", "gemini")
    default_models: dict[str, str] = {
        "gemini": "gemini-3.5-flash",
        "openai": "gpt-5.5",
        "anthropic": "claude-sonnet-4-6",
    }
    model = os.environ.get("HARUNOBU_AI_MODEL", default_models.get(provider, "gemini-3.5-flash"))
    fallback = os.environ.get("HARUNOBU_AI_FALLBACK_MODEL", "gemini-3.5-flash" if provider == "gemini" else None)
    return provider, model, fallback


class AIClient:
    """LiteLLM / google.genai 統一クライアント（シングルトン）。"""

    _instance: AIClient | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AIClient:
        """シングルトンインスタンスを返す（未生成ならスレッドセーフに生成）。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """シングルトンインスタンスを破棄する（テスト・再設定用）。"""
        with cls._lock:
            cls._instance = None

    def __init__(self) -> None:
        self._available: bool | None = None
        self._backend: str | None = None  # "litellm" または "genai"
        self._genai_client: Any = None
        provider, model, fallback = _resolve_ai_config()
        self._provider = provider
        self._model = model
        self._fallback_model = fallback

    # ─── 公開 API ─────────────────────────────────────────────

    def is_available(self) -> bool:
        """AI 機能が利用可能かを返す。"""
        if self._available is not None:
            return self._available
        if os.environ.get("HARUNOBU_AI_DISABLED", "").lower() in ("true", "1"):
            self._available = False
            return False
        try:
            self._detect_backend()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def generate_json(self, prompt: str, *, method_name: str) -> Any | None:
        """テキストプロンプトから JSON レスポンスを取得する。"""
        if not self.is_available():
            return None
        try:
            backend = self._detect_backend()
            if backend == "litellm":
                return self._generate_json_litellm(prompt, method_name)
            return self._generate_json_genai(prompt, method_name)
        except Exception:
            logger.exception("AI generate_json failed (%s)", method_name)
            return None

    def generate_json_with_image(
        self,
        prompt: str,
        image_data: bytes,
        *,
        method_name: str,
        mime_type: str = "image/png",
    ) -> Any | None:
        """テキスト + 画像1枚から JSON レスポンスを取得する。"""
        return self.generate_json_with_images(
            prompt,
            [(mime_type, image_data)],
            method_name=method_name,
        )

    def generate_json_with_images(
        self,
        prompt: str,
        images: list[tuple[str, bytes]],
        *,
        method_name: str,
    ) -> Any | None:
        """テキスト + 複数画像から JSON レスポンスを取得する。"""
        if not self.is_available():
            return None
        try:
            backend = self._detect_backend()
            if backend == "litellm":
                return self._generate_image_litellm(prompt, images, method_name)
            return self._generate_image_genai(prompt, images, method_name)
        except Exception:
            logger.exception("AI generate_json_with_images failed (%s)", method_name)
            return None

    # ─── バックエンド検出 ──────────────────────────────────────

    def _detect_backend(self) -> str:
        if self._backend:
            return self._backend
        # Gemini 以外のプロバイダーは litellm が必須
        if self._provider != "gemini":
            try:
                import litellm  # noqa: F401

                self._backend = "litellm"
                return self._backend
            except ImportError:
                raise ImportError(
                    f"Provider '{self._provider}' requires litellm. Install with: uv sync --extra ai"
                ) from None
        # Gemini: litellm を優先し、無ければ google.genai にフォールバック
        try:
            import litellm  # noqa: F401

            self._backend = "litellm"
        except ImportError:
            try:
                import google.genai  # noqa: F401

                self._backend = "genai"
            except ImportError:
                raise ImportError(
                    "Neither litellm nor google-genai is installed. Install with: uv sync --extra ai"
                ) from None
        return self._backend

    def _get_genai_client(self) -> Any:
        if self._genai_client is None:
            from google import genai

            self._genai_client = genai.Client()
        return self._genai_client

    def _get_litellm_model_id(self, model: str | None = None) -> str:
        m = model or self._model
        if "/" in m:
            return m
        prefix_map = {"gemini": "gemini", "openai": "openai", "anthropic": "anthropic"}
        prefix = prefix_map.get(self._provider, self._provider)
        return f"{prefix}/{m}"

    # ─── LiteLLM バックエンド ────────────────────────────────────────

    @staticmethod
    def _litellm_completion(model_id: str, messages: list[dict[str, Any]]) -> Any:
        """litellm.completion を JSON モードで呼ぶ。

        ``drop_params=True`` で未対応パラメータを除去するが、litellm のモデルマップに
        未登録の新しいモデル（GPT-5 系・Claude Opus 4.x 等）では temperature が
        除去されずエラーになる。その場合は temperature を外して再試行する。

        Args:
            model_id: litellm 形式の model id。
            messages: チャットメッセージ列。

        Returns:
            litellm のレスポンスオブジェクト。
        """
        import litellm

        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "drop_params": True,
        }
        try:
            return litellm.completion(temperature=0.1, **kwargs)
        except Exception as e:
            if "temperature" in str(e).lower():
                logger.info("Model %s rejects temperature; retrying without it", model_id)
                return litellm.completion(**kwargs)
            raise

    def _generate_json_litellm(self, prompt: str, method_name: str) -> Any | None:
        from harunobu.core.ai_metrics import track_ai_call

        model_id = self._get_litellm_model_id()
        with track_ai_call(method_name, model_id) as tracker:
            response = self._litellm_completion(model_id, [{"role": "user", "content": prompt}])
            tracker.set_tokens_from_response(response)
            return _parse_json_response(response.choices[0].message.content)

    def _generate_image_litellm(
        self,
        prompt: str,
        images: list[tuple[str, bytes]],
        method_name: str,
    ) -> Any | None:
        from harunobu.core.ai_metrics import track_ai_call

        content: list[dict[str, Any]] = []
        for mime_type, data in images:
            b64 = base64.b64encode(data).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                }
            )
        content.append({"type": "text", "text": prompt})

        model_id = self._get_litellm_model_id()
        with track_ai_call(method_name, model_id) as tracker:
            response = self._litellm_completion(model_id, [{"role": "user", "content": content}])
            tracker.set_tokens_from_response(response)
            return _parse_json_response(response.choices[0].message.content)

    # ─── google.genai バックエンド ───────────────────────────────────

    def _generate_json_genai(self, prompt: str, method_name: str) -> Any | None:
        from google.genai import types

        from harunobu.core.ai_metrics import track_ai_call

        client = self._get_genai_client()
        models_to_try = [self._model]
        if self._fallback_model:
            models_to_try.append(self._fallback_model)

        for model in models_to_try:
            try:
                with track_ai_call(method_name, model) as tracker:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                        ),
                    )
                    tracker.set_tokens_from_response(response)
                    return _parse_json_response(response.text)
            except Exception:
                if model == models_to_try[-1]:
                    raise
                logger.warning("Model %s failed, trying fallback", model)

    def _generate_image_genai(
        self,
        prompt: str,
        images: list[tuple[str, bytes]],
        method_name: str,
    ) -> Any | None:
        from google.genai import types

        from harunobu.core.ai_metrics import track_ai_call

        client = self._get_genai_client()
        parts: list[Any] = []
        for mime_type, data in images:
            parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        parts.append(types.Part.from_text(text=prompt))

        models_to_try = [self._model]
        if self._fallback_model:
            models_to_try.append(self._fallback_model)

        for model in models_to_try:
            try:
                with track_ai_call(method_name, model) as tracker:
                    response = client.models.generate_content(
                        model=model,
                        contents=types.Content(parts=parts),
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                        ),
                    )
                    tracker.set_tokens_from_response(response)
                    return _parse_json_response(response.text)
            except Exception:
                if model == models_to_try[-1]:
                    raise
                logger.warning("Model %s failed for image, trying fallback", model)
