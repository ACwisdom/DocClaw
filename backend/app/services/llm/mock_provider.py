import re
import time
from collections.abc import Iterator

from ..ai_service import _generate_mock_response
from .base import ChatMessage, LLMResponse


class MockLLMProvider:
    name = "mock"

    def is_available(self) -> bool:
        return True

    def _resolve_user_and_skill(
        self, messages: list[ChatMessage]
    ) -> tuple[str, str, str]:
        user_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_message = msg.content
                break

        system_message = next((m.content for m in messages if m.role == "system"), "")
        skill_name = "智能病历助手"
        if "你是" in system_message:
            first_line = system_message.split("\n", 1)[0].strip()
            if first_line:
                skill_name = first_line.replace("你是", "").strip() or skill_name
        return user_message, system_message, skill_name

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        user_message, system_message, skill_name = self._resolve_user_and_skill(messages)
        content = _generate_mock_response(user_message, system_message, skill_name)
        return LLMResponse(content=content, provider=self.name, model=None)

    def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]:
        response = self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        json_object_mode = bool(
            response_format and response_format.get("type") == "json_object"
        )
        if json_object_mode:
            time.sleep(0.2)
            yield response.content
            return

        parts = re.split(r"(?<=[。！？\n])|(?<=\s)", response.content)
        for part in parts:
            if not part:
                continue
            time.sleep(0.04)
            yield part
