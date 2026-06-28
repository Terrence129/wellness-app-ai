from collections.abc import Callable

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import app.api.dependencies as dependencies
from app.api.dependencies import get_chat_service
from app.core.config import Settings
from app.core.exceptions import AppError
from app.main import create_app
from app.schemas.chat import ChatProviderResult
from app.services.chat import ChatService
from app.services.safety import CRISIS_RESPONSE, SafetyPolicy
from tests.fakes import FakeLLMProvider

REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000"
ERROR_CASES = (
    (AppError.validation_error, 422, "VALIDATION_ERROR", "The request is invalid."),
    (
        AppError.rate_limited,
        429,
        "AI_RATE_LIMITED",
        "The AI provider is busy. Please try again later.",
    ),
    (
        AppError.invalid_response,
        502,
        "AI_INVALID_RESPONSE",
        "The AI provider returned an invalid response.",
    ),
    (
        AppError.provider_request_rejected,
        502,
        "AI_PROVIDER_REQUEST_REJECTED",
        "The AI provider rejected the request.",
    ),
    (
        AppError.provider_not_configured,
        503,
        "AI_PROVIDER_NOT_CONFIGURED",
        "The AI provider is not configured.",
    ),
    (
        AppError.provider_auth_failed,
        503,
        "AI_PROVIDER_AUTH_FAILED",
        "The AI provider authentication failed.",
    ),
    (
        AppError.provider_quota_exhausted,
        503,
        "AI_PROVIDER_QUOTA_EXHAUSTED",
        "The AI provider quota is exhausted.",
    ),
    (
        AppError.provider_unavailable,
        503,
        "AI_PROVIDER_UNAVAILABLE",
        "The AI provider is temporarily unavailable.",
    ),
    (
        AppError.provider_timeout,
        504,
        "AI_PROVIDER_TIMEOUT",
        "The AI provider timed out.",
    ),
    (AppError.internal_error, 500, "INTERNAL_ERROR", "An unexpected error occurred."),
)


def _client(provider: FakeLLMProvider) -> TestClient:
    application = create_app(Settings(DEEPSEEK_API_KEY=" ", _env_file=None))
    service = ChatService(provider, SafetyPolicy())
    application.dependency_overrides[get_chat_service] = lambda: service
    return TestClient(application, raise_server_exceptions=False)


def _post(client: TestClient, payload: dict[str, object] | None = None) -> object:
    body = (
        {"userId": 7, "message": "How can I unwind?", "history": []}
        if payload is None
        else payload
    )
    return client.post("/ai/chat", json=body, headers={"X-Request-ID": REQUEST_ID})


def _assert_error(response: object, status: int, code: str, message: str) -> None:
    assert response.status_code == status  # type: ignore[attr-defined]
    assert response.headers["X-Request-ID"] == REQUEST_ID  # type: ignore[attr-defined]
    assert response.json() == {  # type: ignore[attr-defined]
        "success": False,
        "message": message,
        "errorCode": code,
        "requestId": REQUEST_ID,
    }


def test_chat_returns_exact_aliases_and_matching_request_id() -> None:
    """Expose the normal chat service result unchanged. Author: 2692341798."""
    provider = FakeLLMProvider(
        chat_result=ChatProviderResult(
            content="Take a short walk.", model="deepseek-v4-flash"
        )
    )

    response = _post(_client(provider))

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.json() == {"reply": "Take a short walk.", "requestId": REQUEST_ID}
    assert provider.chat_calls == [
        {"message": "How can I unwind?", "history": [], "knowledge_context": ""}
    ]


def test_chat_crisis_short_circuits_provider() -> None:
    """Return deterministic crisis guidance before provider use. Author: 2692341798."""
    provider = FakeLLMProvider(error=AssertionError("provider must not be called"))

    response = _post(
        _client(provider),
        {"userId": 7, "message": "I want to kill myself", "history": []},
    )

    assert response.status_code == 200
    assert response.json() == {"reply": CRISIS_RESPONSE, "requestId": REQUEST_ID}
    assert provider.chat_calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"userId": 0, "message": "hello"},
        {"userId": 1, "message": "   "},
        {"userId": 1, "message": "hello", "history": [{"role": "system", "content": "x"}]},
    ],
)
def test_chat_invalid_requests_use_global_validation_error(
    payload: dict[str, object],
) -> None:
    """Map invalid chat payloads to the stable global envelope. Author: 2692341798."""
    response = _post(_client(FakeLLMProvider()), payload)

    _assert_error(response, 422, "VALIDATION_ERROR", "The request is invalid.")


@pytest.mark.parametrize(("factory", "status", "code", "message"), ERROR_CASES)
def test_chat_maps_every_app_error_exactly(
    factory: Callable[[], AppError], status: int, code: str, message: str
) -> None:
    """Preserve every declared application error mapping. Author: 2692341798."""
    response = _post(_client(FakeLLMProvider(error=factory())))

    _assert_error(response, status, code, message)


def test_chat_hides_unexpected_service_details() -> None:
    """Hide unexpected chat service implementation details. Author: 2692341798."""
    response = _post(_client(FakeLLMProvider(error=RuntimeError("secret failure"))))

    _assert_error(response, 500, "INTERNAL_ERROR", "An unexpected error occurred.")
    assert "secret failure" not in response.text


def test_chat_without_key_uses_real_dependency_path() -> None:
    """Report missing configuration through the production DI path. Author: 2692341798."""
    application = create_app(Settings(DEEPSEEK_API_KEY=" ", _env_file=None))

    response = _post(TestClient(application, raise_server_exceptions=False))

    _assert_error(
        response,
        503,
        "AI_PROVIDER_NOT_CONFIGURED",
        "The AI provider is not configured.",
    )


def test_dependencies_lazily_construct_and_share_one_provider_per_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construct one provider lazily and share it across services. Author: 2692341798."""
    settings = Settings(DEEPSEEK_API_KEY="test-key", _env_file=None)
    provider = FakeLLMProvider()
    constructed_with: list[Settings] = []

    def construct_provider(resolved_settings: Settings) -> FakeLLMProvider:
        """Record provider construction without creating an SDK. Author: 2692341798."""
        constructed_with.append(resolved_settings)
        return provider

    monkeypatch.setattr(dependencies, "DeepSeekProvider", construct_provider)

    application = create_app(settings)
    assert constructed_with == []

    request = Request({"type": "http", "app": application})
    resolved_settings = dependencies.get_settings(request)
    chat_provider = dependencies.get_provider(request, resolved_settings)
    advice_provider = dependencies.get_provider(request, resolved_settings)
    chat_service = dependencies.get_chat_service(chat_provider, None)
    advice_service = dependencies.get_advice_service(advice_provider)

    assert resolved_settings is settings
    assert constructed_with == [settings]
    assert chat_provider is provider
    assert advice_provider is provider
    assert chat_service._provider is provider
    assert advice_service._provider is provider


def test_dependencies_reuse_preconfigured_app_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reuse an app-owned provider without constructing DeepSeek. Author: 2692341798."""
    settings = Settings(DEEPSEEK_API_KEY="test-key", _env_file=None)
    provider = FakeLLMProvider()
    application = create_app(settings)
    application.state.llm_provider = provider

    def reject_construction(_settings: Settings) -> FakeLLMProvider:
        """Fail if the cached-provider path constructs DeepSeek. Author: 2692341798."""
        raise AssertionError("DeepSeekProvider must not be constructed")

    monkeypatch.setattr(dependencies, "DeepSeekProvider", reject_construction)
    request = Request({"type": "http", "app": application})

    resolved = dependencies.get_provider(request, dependencies.get_settings(request))

    assert resolved is provider
