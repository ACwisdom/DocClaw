from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["mock", "openai_compat"] = "openai_compat"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 60.0
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3
    llm_fallback_to_mock: bool = True
    llm_disable_thinking: bool = True
    llm_stream_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
