from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_advice_service
from app.core.config import Settings
from app.core.exceptions import AppError
from app.main import create_app
from app.schemas.advice import AdviceProviderResult
from app.services.advice import NO_DATA_ADVICE, AdviceService
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
    service = AdviceService(provider)
    application.dependency_overrides[get_advice_service] = lambda: service
    return TestClient(application, raise_server_exceptions=False)


def _post(client: TestClient, payload: dict[str, object] | None = None) -> object:
    body = (
        {
            "userId": 7,
            "logs": [{"logDate": "2026-06-27", "sleepHours": 7.5, "moodScore": 4}],
        }
        if payload is None
        else payload
    )
    return client.post(
        "/ai/wellness-advice", json=body, headers={"X-Request-ID": REQUEST_ID}
    )


def _assert_error(response: object, status: int, code: str, message: str) -> None:
    assert response.status_code == status  # type: ignore[attr-defined]
    assert response.headers["X-Request-ID"] == REQUEST_ID  # type: ignore[attr-defined]
    assert response.json() == {  # type: ignore[attr-defined]
        "success": False,
        "message": message,
        "errorCode": code,
        "requestId": REQUEST_ID,
    }


def test_advice_returns_exact_aliases_and_matching_request_id() -> None:
    """Expose the normal advice service result with aliases. Author: 2692341798."""
    provider = FakeLLMProvider(
        advice_result=AdviceProviderResult(
            advice_text="Keep a regular bedtime.", model="deepseek-v4-flash"
        )
    )

    response = _post(_client(provider))

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.json() == {
        "adviceText": "Keep a regular bedtime.",
        "requestId": REQUEST_ID,
    }
    assert len(provider.advice_calls) == 1


def test_empty_logs_return_fixed_advice_without_provider() -> None:
    """Keep the no-data advice deterministic and offline. Author: 2692341798."""
    provider = FakeLLMProvider(error=AssertionError("provider must not be called"))

    response = _post(_client(provider), {"userId": 7, "logs": []})

    assert response.status_code == 200
    assert response.json() == {"adviceText": NO_DATA_ADVICE, "requestId": REQUEST_ID}
    assert provider.advice_calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"userId": 0, "logs": []},
        {"userId": 1, "logs": [{"logDate": "not-a-date"}]},
        {"userId": 1, "logs": [{"logDate": "2026-06-27", "sleepHours": 25}]},
    ],
)
def test_advice_invalid_requests_use_global_validation_error(
    payload: dict[str, object],
) -> None:
    """Map invalid advice payloads to the stable global envelope. Author: 2692341798."""
    response = _post(_client(FakeLLMProvider()), payload)

    _assert_error(response, 422, "VALIDATION_ERROR", "The request is invalid.")


@pytest.mark.parametrize(("factory", "status", "code", "message"), ERROR_CASES)
def test_advice_maps_every_app_error_exactly(
    factory: Callable[[], AppError], status: int, code: str, message: str
) -> None:
    """Preserve every declared application error mapping. Author: 2692341798."""
    response = _post(_client(FakeLLMProvider(error=factory())))

    _assert_error(response, status, code, message)


def test_advice_hides_unexpected_service_details() -> None:
    """Hide unexpected advice service implementation details. Author: 2692341798."""
    response = _post(_client(FakeLLMProvider(error=RuntimeError("private detail"))))

    _assert_error(response, 500, "INTERNAL_ERROR", "An unexpected error occurred.")
    assert "private detail" not in response.text


def test_empty_logs_without_key_use_real_dependency_path() -> None:
    """Keep no-data advice available through production DI without a key. Author: 2692341798."""
    application = create_app(Settings(DEEPSEEK_API_KEY=" ", _env_file=None))

    response = _post(
        TestClient(application, raise_server_exceptions=False),
        {"userId": 7, "logs": []},
    )

    assert response.status_code == 200
    assert response.json() == {"adviceText": NO_DATA_ADVICE, "requestId": REQUEST_ID}


def test_non_empty_logs_without_key_use_real_dependency_path() -> None:
    """Require provider configuration for generated advice. Author: 2692341798."""
    application = create_app(Settings(DEEPSEEK_API_KEY=" ", _env_file=None))

    response = _post(TestClient(application, raise_server_exceptions=False))

    _assert_error(
        response,
        503,
        "AI_PROVIDER_NOT_CONFIGURED",
        "The AI provider is not configured.",
    )
