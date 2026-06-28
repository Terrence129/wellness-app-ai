from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError, ErrorCode
from app.providers.ollama import OllamaProvider


class FakeOllamaClient:
    def chat(self, **kwargs: object) -> dict[str, object]:
        return {"message": {"content": "hello from ollama"}, "model": "llama3.1"}


def test_settings_expose_local_ollama_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.embed_model == "all-MiniLM-L6-v2"
    assert settings.chat_model == "llama3.1"
    assert settings.ollama_host == "http://localhost:11434"


def test_ollama_provider_initializes_with_local_defaults() -> None:
    client = FakeOllamaClient()
    provider = OllamaProvider(Settings(_env_file=None), client=client)

    assert provider._settings.embed_model == "all-MiniLM-L6-v2"
    assert provider._settings.chat_model == "llama3.1"
    assert provider._settings.ollama_host == "http://localhost:11434"
    assert provider._client is client


def test_ollama_chat_accepts_sdk_attribute_response() -> None:
    """Accept current Ollama SDK response objects. Author: 2692341798."""
    parsed = OllamaProvider._parse_completion(
        SimpleNamespace(
            message=SimpleNamespace(content="  hello from sdk  "),
            model="llama3.1",
            prompt_eval_count=5,
            eval_count=7,
        )
    )

    assert parsed.content == "hello from sdk"
    assert parsed.model == "llama3.1"
    assert parsed.prompt_tokens == 5
    assert parsed.completion_tokens == 7


def test_ollama_chat_accepts_sdk_model_dump_response() -> None:
    """Accept SDK model objects that expose response data through model_dump.

    Author: 2692341798
    """

    class DumpableResponse:
        """Minimal pydantic-like response object. Author: 2692341798."""

        def model_dump(self) -> dict[str, object]:
            """Return an Ollama-compatible response mapping. Author: 2692341798."""
            return {
                "message": {"content": "hello from dump"},
                "model": "llama3.1",
            }

    parsed = OllamaProvider._parse_completion(DumpableResponse())

    assert parsed.content == "hello from dump"


def test_ollama_chat_rejects_missing_message_content() -> None:
    """Reject SDK responses that still lack usable text. Author: 2692341798."""
    with pytest.raises(AppError) as raised:
        OllamaProvider._parse_completion(SimpleNamespace(message=SimpleNamespace()))

    assert raised.value.error_code is ErrorCode.AI_INVALID_RESPONSE
