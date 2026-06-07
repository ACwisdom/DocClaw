import json
from collections.abc import Iterator

import httpx

from ...config import Settings
from .base import ChatMessage, LLMResponse


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, settings: Settings):
        self._settings = settings

    def _is_glm_endpoint(self) -> bool:
        base = self._settings.llm_base_url.lower()
        model = self._settings.llm_model.lower()
        return "bigmodel.cn" in base or "z.ai" in base or model.startswith("glm")

    def is_available(self) -> bool:
        return bool(self._settings.llm_api_key.strip())

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        stream: bool = False,
    ) -> dict:
        payload: dict = {
            "model": self._settings.llm_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature if temperature is not None else self._settings.llm_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._settings.llm_max_tokens,
        }
        if stream:
            payload["stream"] = True
        if self._settings.llm_disable_thinking and self._is_glm_endpoint():
            payload["thinking"] = {"type": "disabled"}
        if response_format:
            payload["response_format"] = response_format
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }

    def _extract_delta(self, data: dict) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return delta.get("content") or delta.get("reasoning_content") or ""

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("LLM API key 未配置")

        url = f"{self._settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = self._build_payload(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        with httpx.Client(timeout=self._settings.llm_timeout) as client:
            response = client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError("LLM 返回内容为空")
        return LLMResponse(
            content=content,
            provider=self.name,
            model=data.get("model") or self._settings.llm_model,
        )

    def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]:
        if not self.is_available():
            raise RuntimeError("LLM API key 未配置")

        url = f"{self._settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = self._build_payload(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=True,
        )
        json_object_mode = bool(
            response_format and response_format.get("type") == "json_object"
        )
        buffer = ""

        with httpx.Client(timeout=self._settings.llm_timeout) as client:
            with client.stream("POST", url, json=payload, headers=self._headers()) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    delta = self._extract_delta(data)
                    if not delta:
                        continue
                    buffer += delta
                    if not json_object_mode:
                        yield delta

        if json_object_mode and buffer.strip():
            yield buffer
