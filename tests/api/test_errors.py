from fastapi import Query
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import create_app


def _client_with_error_routes() -> TestClient:
    application = create_app()

    @application.get("/validate")
    async def validate(value: int = Query(gt=0)) -> dict[str, int]:
        return {"value": value}

    @application.get("/app-error")
    async def app_error() -> None:
        raise AppError.provider_unavailable()

    @application.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("sensitive implementation detail")

    return TestClient(application, raise_server_exceptions=False)


def _assert_error(
    response: object, *, status: int, message: str, error_code: str
) -> None:
    assert response.status_code == status  # type: ignore[attr-defined]
    request_id = response.headers["X-Request-ID"]  # type: ignore[attr-defined]
    assert response.json() == {  # type: ignore[attr-defined]
        "success": False,
        "message": message,
        "errorCode": error_code,
        "requestId": request_id,
    }


def test_validation_errors_use_stable_envelope() -> None:
    response = _client_with_error_routes().get("/validate", params={"value": 0})

    _assert_error(
        response,
        status=422,
        message="The request is invalid.",
        error_code="VALIDATION_ERROR",
    )


def test_app_errors_use_stable_envelope() -> None:
    response = _client_with_error_routes().get("/app-error")

    _assert_error(
        response,
        status=503,
        message="The AI provider is temporarily unavailable.",
        error_code="AI_PROVIDER_UNAVAILABLE",
    )


def test_unexpected_errors_hide_internal_details() -> None:
    request_id = "550e8400-e29b-41d4-a716-446655440000"
    response = _client_with_error_routes().get(
        "/unexpected", headers={"X-Request-ID": request_id}
    )

    _assert_error(
        response,
        status=500,
        message="An unexpected error occurred.",
        error_code="INTERNAL_ERROR",
    )
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["requestId"] == request_id
    assert "sensitive implementation detail" not in response.text
