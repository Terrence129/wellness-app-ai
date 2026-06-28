from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated process configuration.

    Author: 2692341798
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = Field("wellness-app-ai", validation_alias="APP_NAME")
    app_env: str = Field("development", validation_alias="APP_ENV")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    deepseek_api_key: str | None = Field(None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        "https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL"
    )
    embed_model: str = Field("all-MiniLM-L6-v2", validation_alias="EMBED_MODEL")
    chat_model: str = Field("llama3.1", validation_alias="CHAT_MODEL")
    ollama_host: str = Field("http://localhost:11434", validation_alias="OLLAMA_HOST")
    deepseek_chat_model: str = Field(
        "deepseek-v4-flash", validation_alias="DEEPSEEK_CHAT_MODEL"
    )
    deepseek_advice_model: str = Field(
        "deepseek-v4-flash", validation_alias="DEEPSEEK_ADVICE_MODEL"
    )
    deepseek_agent_model: str = Field(
        "deepseek-v4-pro", validation_alias="DEEPSEEK_AGENT_MODEL"
    )
    deepseek_timeout_seconds: float = Field(
        30, ge=1, le=120, validation_alias="DEEPSEEK_TIMEOUT_SECONDS"
    )
    deepseek_max_retries: int = Field(
        2, ge=0, le=5, validation_alias="DEEPSEEK_MAX_RETRIES"
    )

    @field_validator("deepseek_api_key", mode="before")
    @classmethod
    def blank_key_is_unconfigured(cls, value: Any) -> Any:
        """Trim configured keys and treat whitespace-only values as missing.

        Author: 2692341798
        """
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value
