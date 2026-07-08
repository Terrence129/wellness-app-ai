# Author: Huang Qijun
# Email: 2692341798@qq.com

from uuid import UUID

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_works_without_provider_configuration() -> None:
    application = create_app(Settings(DEEPSEEK_API_KEY=" ", _env_file=None))
    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "wellness-app-ai"}
    assert str(UUID(response.headers["X-Request-ID"])) == response.headers["X-Request-ID"]


def test_valid_client_request_id_is_echoed() -> None:
    request_id = "550e8400-e29b-41d4-a716-446655440000"
    response = TestClient(create_app()).get("/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


def test_invalid_client_request_id_is_replaced() -> None:
    response = TestClient(create_app()).get(
        "/health", headers={"X-Request-ID": "not-a-valid-uuid"}
    )

    generated = response.headers["X-Request-ID"]
    assert generated != "not-a-valid-uuid"
    assert str(UUID(generated)) == generated


def test_factory_stores_settings_and_does_not_enable_cors() -> None:
    settings = Settings(APP_ENV="test", _env_file=None)
    application = create_app(settings)

    assert application.state.settings is settings
    assert all(middleware.cls is not CORSMiddleware for middleware in application.user_middleware)
