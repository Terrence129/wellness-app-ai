# Author: Huang Qijun
# Email: 2692341798@qq.com

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_use_safe_defaults_without_api_key() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "wellness-app-ai"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.deepseek_api_key is None
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_chat_model == "deepseek-v4-flash"
    assert settings.deepseek_advice_model == "deepseek-v4-flash"
    assert settings.deepseek_agent_model == "deepseek-v4-pro"
    assert settings.deepseek_timeout_seconds == 30.0
    assert settings.deepseek_max_retries == 2
    assert settings.rag_enabled is True
    assert settings.rag_knowledge_dir == "knowledge"
    assert settings.rag_index_path == ".data/rag-index.sqlite3"
    assert settings.rag_top_k == 4
    assert settings.rag_chunk_size == 1000
    assert settings.rag_chunk_overlap == 150
    assert settings.rag_context_max_chars == 4000
    assert settings.rag_max_file_bytes == 1_048_576
    assert settings.rag_max_corpus_bytes == 20_971_520


def test_settings_accept_environment_aliases() -> None:
    settings = Settings(
        APP_NAME="custom-ai",
        APP_ENV="test",
        LOG_LEVEL="DEBUG",
        DEEPSEEK_API_KEY="secret",
        DEEPSEEK_TIMEOUT_SECONDS=45,
        DEEPSEEK_MAX_RETRIES=4,
        _env_file=None,
    )

    assert settings.app_name == "custom-ai"
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.deepseek_api_key == "secret"
    assert settings.deepseek_timeout_seconds == 45.0
    assert settings.deepseek_max_retries == 4


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_blank_api_key_is_unconfigured(value: str) -> None:
    assert Settings(DEEPSEEK_API_KEY=value, _env_file=None).deepseek_api_key is None


def test_api_key_is_trimmed() -> None:
    assert Settings(DEEPSEEK_API_KEY="  secret  ", _env_file=None).deepseek_api_key == "secret"


@pytest.mark.parametrize("value", [0, 121])
def test_timeout_must_be_within_supported_range(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(DEEPSEEK_TIMEOUT_SECONDS=value, _env_file=None)


@pytest.mark.parametrize("value", [-1, 6])
def test_retry_count_must_be_within_supported_range(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(DEEPSEEK_MAX_RETRIES=value, _env_file=None)


def test_rag_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(
            RAG_CHUNK_SIZE="300",
            RAG_CHUNK_OVERLAP="300",
            _env_file=None,
        )


def test_rag_file_limit_must_not_exceed_corpus_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(
            RAG_MAX_FILE_BYTES="2000",
            RAG_MAX_CORPUS_BYTES="1000",
            _env_file=None,
        )
