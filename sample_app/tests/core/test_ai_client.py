"""AIClient の JSON 応答パースに関するテスト。

API を叩かず、純粋関数（コードフェンス除去・JSON 解釈）の挙動を検証する。
"""

from __future__ import annotations

import pytest

from harunobu.core.ai_client import AIClient, _parse_json_response, _strip_code_fence


class Test_strip_code_fence:
    """`_strip_code_fence` のテスト。"""

    def test_フェンス無しはそのまま返す(self) -> None:
        assert _strip_code_fence('{"ok": true}') == '{"ok": true}'

    def test_前後の空白を除去する(self) -> None:
        assert _strip_code_fence('  {"ok": true}\n') == '{"ok": true}'

    def test_json付きフェンスを除去する(self) -> None:
        text = '```json\n{"ok": true, "n": 7}\n```'
        assert _strip_code_fence(text) == '{"ok": true, "n": 7}'

    def test_言語指定なしフェンスを除去する(self) -> None:
        text = '```\n{"ok": true}\n```'
        assert _strip_code_fence(text) == '{"ok": true}'

    def test_フェンス周辺の余分な空白を許容する(self) -> None:
        text = '  ```json\n{"a": 1}\n```  '
        assert _strip_code_fence(text) == '{"a": 1}'


class Test_parse_json_response:
    """`_parse_json_response` のテスト。"""

    def test_素のjsonを解釈する(self) -> None:
        assert _parse_json_response('{"ok": true, "n": 7}') == {"ok": True, "n": 7}

    def test_フェンス付きjsonを解釈する(self) -> None:
        # Anthropic claude-4.x が返しがちな形式
        text = '```json\n{"ok": true, "n": 7}\n```'
        assert _parse_json_response(text) == {"ok": True, "n": 7}

    @pytest.mark.parametrize("empty", [None, "", "   ", "\n"])
    def test_空応答はNoneを返す(self, empty: str | None) -> None:
        assert _parse_json_response(empty) is None

    def test_不正なjsonは例外を送出する(self) -> None:
        with pytest.raises(ValueError):
            _parse_json_response("not json at all")


class Test_litellm_completion:
    """`_litellm_completion`（temperature フォールバック）のテスト。"""

    def _patch_litellm(self, monkeypatch: pytest.MonkeyPatch, fake: object) -> None:
        import sys
        import types

        module = types.ModuleType("litellm")
        module.completion = fake  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "litellm", module)

    def test_通常はtemperature付きで呼ぶ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake(**kwargs):  # noqa: ANN003, ANN202
            calls.append(kwargs)
            return "resp"

        self._patch_litellm(monkeypatch, fake)
        result = AIClient._litellm_completion("openai/gpt-4o", [{"role": "user", "content": "x"}])

        assert result == "resp"
        assert len(calls) == 1
        assert calls[0]["temperature"] == 0.1

    def test_temperature非対応なら外して再試行する(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake(**kwargs):  # noqa: ANN003, ANN202
            calls.append(kwargs)
            if "temperature" in kwargs:
                raise ValueError("`temperature` is deprecated for this model.")
            return "resp"

        self._patch_litellm(monkeypatch, fake)
        result = AIClient._litellm_completion("anthropic/claude-opus-4-8", [{"role": "user", "content": "x"}])

        assert result == "resp"
        assert len(calls) == 2
        assert "temperature" not in calls[1]

    def test_temperature以外のエラーは送出する(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake(**kwargs):  # noqa: ANN003, ANN202
            raise ValueError("authentication failed")

        self._patch_litellm(monkeypatch, fake)
        with pytest.raises(ValueError, match="authentication"):
            AIClient._litellm_completion("openai/gpt-4o", [{"role": "user", "content": "x"}])
