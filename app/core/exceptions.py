# Author: Huang Qijun
# Email: 2692341798@qq.com

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class ErrorCode(StrEnum):
    """Stable public application error codes.

    Author: 2692341798
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AI_RATE_LIMITED = "AI_RATE_LIMITED"
    AI_INVALID_RESPONSE = "AI_INVALID_RESPONSE"
    AI_PROVIDER_REQUEST_REJECTED = "AI_PROVIDER_REQUEST_REJECTED"
    AI_PROVIDER_NOT_CONFIGURED = "AI_PROVIDER_NOT_CONFIGURED"
    AI_PROVIDER_AUTH_FAILED = "AI_PROVIDER_AUTH_FAILED"
    AI_PROVIDER_QUOTA_EXHAUSTED = "AI_PROVIDER_QUOTA_EXHAUSTED"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_PROVIDER_TIMEOUT = "AI_PROVIDER_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    """Immutable public status and message for one error code.

    Author: 2692341798
    """

    status_code: int
    message: str


ERROR_SPECS = MappingProxyType(
    {
        ErrorCode.VALIDATION_ERROR: ErrorSpec(422, "The request is invalid."),
        ErrorCode.AI_RATE_LIMITED: ErrorSpec(
            429, "The AI provider is busy. Please try again later."
        ),
        ErrorCode.AI_INVALID_RESPONSE: ErrorSpec(
            502, "The AI provider returned an invalid response."
        ),
        ErrorCode.AI_PROVIDER_REQUEST_REJECTED: ErrorSpec(
            502, "The AI provider rejected the request."
        ),
        ErrorCode.AI_PROVIDER_NOT_CONFIGURED: ErrorSpec(
            503, "The AI provider is not configured."
        ),
        ErrorCode.AI_PROVIDER_AUTH_FAILED: ErrorSpec(
            503, "The AI provider authentication failed."
        ),
        ErrorCode.AI_PROVIDER_QUOTA_EXHAUSTED: ErrorSpec(
            503, "The AI provider quota is exhausted."
        ),
        ErrorCode.AI_PROVIDER_UNAVAILABLE: ErrorSpec(
            503, "The AI provider is temporarily unavailable."
        ),
        ErrorCode.AI_PROVIDER_TIMEOUT: ErrorSpec(504, "The AI provider timed out."),
        ErrorCode.INTERNAL_ERROR: ErrorSpec(500, "An unexpected error occurred."),
    }
)


class AppError(Exception):
    """An application failure safe to expose through the HTTP contract.

    Author: 2692341798
    """

    def __init__(self, error_code: ErrorCode) -> None:
        """Build an error exclusively from the locked public mapping.

        Author: 2692341798
        """
        spec = ERROR_SPECS[error_code]
        super().__init__(spec.message)
        self.status_code = spec.status_code
        self.error_code = error_code
        self.message = spec.message

    @classmethod
    def validation_error(cls) -> "AppError":
        """Create a local request-validation error. Author: 2692341798."""
        return cls(ErrorCode.VALIDATION_ERROR)

    @classmethod
    def rate_limited(cls) -> "AppError":
        """Create a provider rate-limit error. Author: 2692341798."""
        return cls(ErrorCode.AI_RATE_LIMITED)

    @classmethod
    def invalid_response(cls) -> "AppError":
        """Create an invalid provider-response error. Author: 2692341798."""
        return cls(ErrorCode.AI_INVALID_RESPONSE)

    @classmethod
    def provider_request_rejected(cls) -> "AppError":
        """Create a rejected provider-payload error. Author: 2692341798."""
        return cls(ErrorCode.AI_PROVIDER_REQUEST_REJECTED)

    @classmethod
    def provider_not_configured(cls) -> "AppError":
        """Create a missing-provider-configuration error. Author: 2692341798."""
        return cls(ErrorCode.AI_PROVIDER_NOT_CONFIGURED)

    @classmethod
    def provider_auth_failed(cls) -> "AppError":
        """Create a provider-authentication error. Author: 2692341798."""
        return cls(ErrorCode.AI_PROVIDER_AUTH_FAILED)

    @classmethod
    def provider_quota_exhausted(cls) -> "AppError":
        """Create a provider-quota error. Author: 2692341798."""
        return cls(ErrorCode.AI_PROVIDER_QUOTA_EXHAUSTED)

    @classmethod
    def provider_unavailable(cls) -> "AppError":
        """Create a provider-unavailable error. Author: 2692341798."""
        return cls(ErrorCode.AI_PROVIDER_UNAVAILABLE)

    @classmethod
    def provider_timeout(cls) -> "AppError":
        """Create a provider-timeout error. Author: 2692341798."""
        return cls(ErrorCode.AI_PROVIDER_TIMEOUT)

    @classmethod
    def internal_error(cls) -> "AppError":
        """Create a generic unexpected-application error. Author: 2692341798."""
        return cls(ErrorCode.INTERNAL_ERROR)
