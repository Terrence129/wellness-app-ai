# Author: Huang Qijun
# Email: 2692341798@qq.com

import json
import logging
from uuid import UUID

from app.core.logging import (
    JsonFormatter,
    configure_logging,
    get_request_id,
    log_event,
    new_request_id,
)


def test_new_request_id_accepts_only_parseable_uuid() -> None:
    supplied = "550e8400-e29b-41d4-a716-446655440000"

    assert new_request_id(supplied) == supplied
    generated = new_request_id("attacker-controlled-id")
    assert generated != "attacker-controlled-id"
    assert str(UUID(generated)) == generated


def test_request_id_context_defaults_to_none() -> None:
    assert get_request_id() is None


def test_configure_logging_replaces_handlers_and_disables_propagation() -> None:
    logger = logging.getLogger("wellness_app")
    stale_handler = logging.NullHandler()
    logger.handlers = [stale_handler]
    logger.propagate = True

    configured = configure_logging("WARNING")

    assert configured is logger
    assert configured.level == logging.WARNING
    assert configured.propagate is False
    assert len(configured.handlers) == 1
    assert configured.handlers[0] is not stale_handler
    assert isinstance(configured.handlers[0], logging.StreamHandler)
    assert isinstance(configured.handlers[0].formatter, JsonFormatter)


def test_json_formatter_emits_only_privacy_allowlisted_fields() -> None:
    logger = logging.getLogger("tests.privacy")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        1,
        "ignored raw message sentinel",
        (),
        None,
        extra={
            "event": "request_completed",
            "request_id": "request-id",
            "method": "POST",
            "path": "/ai/chat",
            "status": 200,
            "latency_ms": 1.5,
            "model": "deepseek-v4-flash",
            "retry_count": 0,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "authorization": "secret bearer sentinel",
            "message_body": "private wellness sentinel",
        },
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload == {
        "event": "request_completed",
        "request_id": "request-id",
        "method": "POST",
        "path": "/ai/chat",
        "status": 200,
        "latency_ms": 1.5,
        "model": "deepseek-v4-flash",
        "retry_count": 0,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_log_event_discards_non_allowlisted_values(caplog: object) -> None:
    logger = logging.getLogger("tests.log_event")
    with caplog.at_level(logging.INFO, logger=logger.name):  # type: ignore[attr-defined]
        log_event(logger, "provider_completed", model="model", raw_text="private sentinel")

    assert "provider_completed" in caplog.text  # type: ignore[attr-defined]
    assert "private sentinel" not in caplog.text  # type: ignore[attr-defined]
