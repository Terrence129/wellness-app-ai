from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.routes.advice import router as advice_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import (
    REQUEST_ID_HEADER,
    configure_logging,
    get_request_id,
    log_event,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from app.schemas.common import ErrorResponse


def _error_response(error: AppError) -> JSONResponse:
    request_id = get_request_id() or new_request_id()
    body = ErrorResponse(
        message=error.message,
        error_code=error.error_code,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(by_alias=True),
        headers={REQUEST_ID_HEADER: request_id},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI service with shared infrastructure and routes.

    Author: 2692341798
    """
    resolved_settings = settings or Settings()
    application = FastAPI(title=resolved_settings.app_name)
    application.state.settings = resolved_settings
    logger = configure_logging(resolved_settings.log_level)

    @application.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bind, emit, and safely reset per-request observability context.

        Author: 2692341798
        """
        request_id = new_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = set_request_id(request_id)
        started = perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                log_event(logger, "unexpected_error")
                response = _error_response(AppError.internal_error())
            response.headers[REQUEST_ID_HEADER] = request_id
            log_event(
                logger,
                "request_completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=round((perf_counter() - started) * 1000, 3),
            )
            return response
        finally:
            reset_request_id(token)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        """Convert framework validation failures to the stable envelope.

        Author: 2692341798
        """
        return _error_response(AppError.validation_error())

    @application.exception_handler(AppError)
    async def app_exception_handler(_request: Request, exc: AppError) -> JSONResponse:
        """Render a safe application error using its locked public mapping.

        Author: 2692341798
        """
        return _error_response(exc)

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
        """Hide unexpected implementation details behind a generic error.

        Author: 2692341798
        """
        log_event(logger, "unexpected_error")
        return _error_response(AppError.internal_error())

    application.include_router(health_router)
    application.include_router(chat_router)
    application.include_router(advice_router)
    return application


app = create_app()
