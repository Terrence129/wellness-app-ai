# Author: Huang Qijun
# Email: 2692341798@qq.com

from typing import Any, Self

from pydantic import Field, field_validator, model_validator
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

    rag_enabled: bool = Field(True, validation_alias="RAG_ENABLED")
    rag_knowledge_dir: str = Field("knowledge", validation_alias="RAG_KNOWLEDGE_DIR")
    rag_index_path: str = Field(
        ".data/rag-index.sqlite3", validation_alias="RAG_INDEX_PATH"
    )
    rag_top_k: int = Field(4, ge=1, le=10, validation_alias="RAG_TOP_K")
    rag_chunk_size: int = Field(
        1000, ge=300, le=4000, validation_alias="RAG_CHUNK_SIZE"
    )
    rag_chunk_overlap: int = Field(
        150, ge=0, validation_alias="RAG_CHUNK_OVERLAP"
    )
    rag_context_max_chars: int = Field(
        4000, ge=500, le=12000, validation_alias="RAG_CONTEXT_MAX_CHARS"
    )
    rag_max_file_bytes: int = Field(
        1_048_576, validation_alias="RAG_MAX_FILE_BYTES"
    )
    rag_max_corpus_bytes: int = Field(
        20_971_520, validation_alias="RAG_MAX_CORPUS_BYTES"
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

    @model_validator(mode="after")
    def _validate_rag_constraints(self) -> Self:
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError(
                "RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE"
            )
        if self.rag_max_file_bytes > self.rag_max_corpus_bytes:
            raise ValueError(
                "RAG_MAX_FILE_BYTES must not exceed RAG_MAX_CORPUS_BYTES"
            )
        return self
