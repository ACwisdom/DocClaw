from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str | None = None
    used_fallback: bool = False


class LLMProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse: ...

    def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]: ...
