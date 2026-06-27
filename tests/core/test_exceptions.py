import pytest

from app.core.exceptions import ERROR_SPECS, AppError, ErrorCode
from app.schemas.common import ErrorResponse

EXPECTED_ERRORS = {
    ErrorCode.VALIDATION_ERROR: (422, "The request is invalid."),
    ErrorCode.AI_RATE_LIMITED: (429, "The AI provider is busy. Please try again later."),
    ErrorCode.AI_INVALID_RESPONSE: (502, "The AI provider returned an invalid response."),
    ErrorCode.AI_PROVIDER_REQUEST_REJECTED: (502, "The AI provider rejected the request."),
    ErrorCode.AI_PROVIDER_NOT_CONFIGURED: (503, "The AI provider is not configured."),
    ErrorCode.AI_PROVIDER_AUTH_FAILED: (503, "The AI provider authentication failed."),
    ErrorCode.AI_PROVIDER_QUOTA_EXHAUSTED: (503, "The AI provider quota is exhausted."),
    ErrorCode.AI_PROVIDER_UNAVAILABLE: (503, "The AI provider is temporarily unavailable."),
    ErrorCode.AI_PROVIDER_TIMEOUT: (504, "The AI provider timed out."),
    ErrorCode.INTERNAL_ERROR: (500, "An unexpected error occurred."),
}


def test_error_mapping_is_complete_and_stable() -> None:
    assert set(ERROR_SPECS) == set(ErrorCode)
    assert {
        code: (spec.status_code, spec.message) for code, spec in ERROR_SPECS.items()
    } == EXPECTED_ERRORS


@pytest.mark.parametrize(
    ("constructor", "code"),
    [
        (AppError.validation_error, ErrorCode.VALIDATION_ERROR),
        (AppError.rate_limited, ErrorCode.AI_RATE_LIMITED),
        (AppError.invalid_response, ErrorCode.AI_INVALID_RESPONSE),
        (AppError.provider_request_rejected, ErrorCode.AI_PROVIDER_REQUEST_REJECTED),
        (AppError.provider_not_configured, ErrorCode.AI_PROVIDER_NOT_CONFIGURED),
        (AppError.provider_auth_failed, ErrorCode.AI_PROVIDER_AUTH_FAILED),
        (AppError.provider_quota_exhausted, ErrorCode.AI_PROVIDER_QUOTA_EXHAUSTED),
        (AppError.provider_unavailable, ErrorCode.AI_PROVIDER_UNAVAILABLE),
        (AppError.provider_timeout, ErrorCode.AI_PROVIDER_TIMEOUT),
        (AppError.internal_error, ErrorCode.INTERNAL_ERROR),
    ],
)
def test_named_constructors_use_locked_mapping(
    constructor: object, code: ErrorCode
) -> None:
    error = constructor()  # type: ignore[operator]
    expected_status, expected_message = EXPECTED_ERRORS[code]

    assert error.status_code == expected_status
    assert error.error_code is code
    assert error.message == expected_message
    assert "cause" not in error.__dict__


def test_error_response_serializes_camel_case_aliases() -> None:
    response = ErrorResponse(
        message="The request is invalid.",
        error_code=ErrorCode.VALIDATION_ERROR,
        request_id="550e8400-e29b-41d4-a716-446655440000",
    )

    assert response.model_dump(by_alias=True) == {
        "success": False,
        "message": "The request is invalid.",
        "errorCode": "VALIDATION_ERROR",
        "requestId": "550e8400-e29b-41d4-a716-446655440000",
    }
