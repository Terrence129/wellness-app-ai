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
