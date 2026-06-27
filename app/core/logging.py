import json
import logging
from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID, uuid4

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_LOG_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "status",
    "latency_ms",
    "model",
    "retry_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
)


class JsonFormatter(logging.Formatter):
    """Serialize only explicitly privacy-approved observability fields.

    Author: 2692341798
    """

    def format(self, record: logging.LogRecord) -> str:
        """Return one JSON object containing allowlisted fields only.

        Author: 2692341798
        """
        payload = {
            field: getattr(record, field)
            for field in _LOG_FIELDS
            if getattr(record, field, None) is not None
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the service JSON logger.

    Author: 2692341798
    """
    logger = logging.getLogger("wellness_app")
    logger.setLevel(level.upper())
    logger.propagate = False
    for existing_handler in logger.handlers[:]:
        logger.removeHandler(existing_handler)
        existing_handler.close()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


def new_request_id(candidate: str | None = None) -> str:
    """Preserve a parseable inbound UUID or generate a canonical UUID.

    Author: 2692341798
    """
    if candidate:
        try:
            UUID(candidate)
        except (ValueError, AttributeError):
            pass
        else:
            return candidate
    return str(uuid4())


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind a request ID to the current async context.

    Author: 2692341798
    """
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the request context represented by a token.

    Author: 2692341798
    """
    _request_id.reset(token)


def get_request_id() -> str | None:
    """Return the request ID bound to the current async context.

    Author: 2692341798
    """
    return _request_id.get()


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an event after discarding all non-allowlisted values.

    Author: 2692341798
    """
    approved = {field: value for field, value in fields.items() if field in _LOG_FIELDS}
    approved["event"] = event
    approved.setdefault("request_id", get_request_id())
    logger.info(event, extra=approved)
