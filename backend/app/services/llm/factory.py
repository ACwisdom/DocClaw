from collections.abc import Iterator
from functools import lru_cache

from ...config import Settings, get_settings
from .base import ChatMessage, LLMResponse
from .mock_provider import MockLLMProvider
from .openai_compat import OpenAICompatProvider


class FallbackLLMProvider:
    """优先使用配置的 Provider，失败或无 Key 时降级到 mock。"""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._primary = (
            MockLLMProvider()
            if settings.llm_provider == "mock"
            else OpenAICompatProvider(settings)
        )
        self._fallback = MockLLMProvider()

    @property
    def name(self) -> str:
        return self._primary.name

    def is_available(self) -> bool:
        return self._primary.is_available() or self._fallback.is_available()

    def active_provider(self) -> str:
        if self._settings.llm_provider == "mock":
            return "mock"
        if self._primary.is_available():
            return self._primary.name
        if self._settings.llm_fallback_to_mock:
            return "mock"
        return self._primary.name

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        if self._settings.llm_provider == "mock":
            return self._fallback.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )

        if not self._primary.is_available():
            if self._settings.llm_fallback_to_mock:
                result = self._fallback.chat(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
                result.used_fallback = True
                return result
            raise RuntimeError("LLM API key 未配置，且未启用 fallback")

        try:
            return self._primary.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception:
            if not self._settings.llm_fallback_to_mock:
                raise
            result = self._fallback.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            result.used_fallback = True
            return result

    def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]:
        if self._settings.llm_provider == "mock":
            yield from self._fallback.chat_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            return

        if not self._primary.is_available():
            if self._settings.llm_fallback_to_mock:
                yield from self._fallback.chat_stream(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
                return
            raise RuntimeError("LLM API key 未配置，且未启用 fallback")

        try:
            yield from self._primary.chat_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception:
            if not self._settings.llm_fallback_to_mock:
                raise
            yield from self._fallback.chat_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )


@lru_cache
def get_llm_provider() -> FallbackLLMProvider:
    return FallbackLLMProvider(get_settings())
