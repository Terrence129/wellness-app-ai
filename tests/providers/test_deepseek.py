# Author: Huang Qijun
# Email: 2692341798@qq.com

import asyncio
import json
import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
)

from app.core.config import Settings
from app.core.exceptions import AppError, ErrorCode
from app.prompts.advice import ADVICE_SYSTEM_PROMPT
from app.prompts.chat import CHAT_SYSTEM_PROMPT
from app.providers import deepseek as deepseek_module
from app.providers.deepseek import DeepSeekProvider
from app.schemas.advice import WellnessLog
from app.schemas.chat import HistoryItem, HistoryRole


class FakeClock:
    """Controllable monotonic clock for retry tests. Author: 2692341798."""

    def __init__(self) -> None:
        """Start at zero. Author: 2692341798."""
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        """Return the current time. Author: 2692341798."""
        return self.now

    async def sleep(self, delay: float) -> None:
        """Advance time by the requested delay. Author: 2692341798."""
        self.sleeps.append(delay)
        self.now += delay


class FakeCompletions:
    """Scripted chat-completions endpoint. Author: 2692341798."""

    def __init__(self, outcomes: list[object]) -> None:
        """Store response or exception outcomes. Author: 2692341798."""
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> object:
        """Record the request and return the next outcome. Author: 2692341798."""
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome()
        return outcome


class FakeClient:
    """Minimal injected OpenAI-compatible client. Author: 2692341798."""

    def __init__(self, outcomes: list[object]) -> None:
        """Expose a scripted completions endpoint. Author: 2692341798."""
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))


class HangingCompletions:
    """Completion endpoint that waits forever unless cancelled. Author: 2692341798."""

    def __init__(self) -> None:
        """Track calls and cancellation. Author: 2692341798."""
        self.calls: list[dict[str, Any]] = []
        self.cancelled = False

    async def create(self, **kwargs: Any) -> object:
        """Wait indefinitely and observe cancellation. Author: 2692341798."""
        self.calls.append(kwargs)
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled = True
        raise AssertionError("unreachable")


def completion(
    content: object,
    *,
    model: str = "served-model",
    finish_reason: str = "stop",
    prompt_tokens: int | None = 11,
    completion_tokens: int | None = 7,
) -> object:
    """Build a minimal SDK-shaped completion. Author: 2692341798."""
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    choice = SimpleNamespace(
        message=SimpleNamespace(content=content),
        finish_reason=finish_reason,
    )
    return SimpleNamespace(choices=[choice], model=model, usage=usage)


def status_error(status: int, retry_after: str | None = None) -> APIStatusError:
    """Build an SDK status error without sensitive content. Author: 2692341798."""
    request = httpx.Request("POST", "https://provider.invalid/chat/completions")
    headers = {"Retry-After": retry_after} if retry_after is not None else None
    response = httpx.Response(status, request=request, headers=headers)
    return APIStatusError("provider failure", response=response, body=None)


def settings(*, retries: int = 2, timeout: float = 30, key: str | None = "secret") -> Settings:
    """Build isolated provider settings. Author: 2692341798."""
    return Settings(
        _env_file=None,
        DEEPSEEK_API_KEY=key,
        DEEPSEEK_MAX_RETRIES=retries,
        DEEPSEEK_TIMEOUT_SECONDS=timeout,
    )


def provider(
    outcomes: list[object],
    *,
    retries: int = 2,
    timeout: float = 30,
    clock: FakeClock | None = None,
    random: Callable[[], float] = lambda: 0.0,
) -> tuple[DeepSeekProvider, FakeClient, FakeClock]:
    """Build a provider with deterministic collaborators. Author: 2692341798."""
    fake_clock = clock or FakeClock()
    client = FakeClient(outcomes)
    instance = DeepSeekProvider(
        settings(retries=retries, timeout=timeout),
        client=client,
        sleep=fake_clock.sleep,
        random=random,
        clock=fake_clock,
    )
    return instance, client, fake_clock


@pytest.mark.asyncio
async def test_chat_sends_safe_payload_and_extracts_usage() -> None:
    """Chat sends only approved fields and parses usage. Author: 2692341798."""
    instance, client, _ = provider([completion("  Take a walk.  ")])
    history = [
        HistoryItem(role=HistoryRole.USER, content="Earlier question"),
        HistoryItem(role=HistoryRole.ASSISTANT, content="Earlier answer"),
    ]

    result = await instance.generate_chat(message="Current question", history=history)

    assert result.content == "Take a walk."
    assert result.model == "served-model"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    call = client.chat.completions.calls[0]
    assert call == {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "Current question"},
        ],
        "extra_body": {"thinking": {"type": "disabled"}},
        "stream": False,
        "timeout": 30.0,
    }
    assert "user" not in call
    assert "userId" not in json.dumps(call)


@pytest.mark.asyncio
async def test_advice_serializes_aliases_and_dates_and_parses_json() -> None:
    """Advice uses JSON mode and strict response validation. Author: 2692341798."""
    instance, client, _ = provider([completion('{"adviceText":"  Hydrate.  "}')])
    log = WellnessLog(logDate="2026-06-27", sleepHours=7.5, moodScore=4)

    result = await instance.generate_advice(logs=[log])

    assert result.advice_text == "Hydrate."
    assert result.model == "served-model"
    call = client.chat.completions.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["messages"][0] == {"role": "system", "content": ADVICE_SYSTEM_PROMPT}
    payload = json.loads(call["messages"][1]["content"])
    assert payload == {
        "logs": [
            {
                "logDate": "2026-06-27",
                "sleepHours": 7.5,
                "moodScore": 4,
                "waterCups": None,
                "steps": None,
                "exerciseMinutes": None,
                "note": None,
            }
        ]
    }
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert call["stream"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["chat", "advice"])
async def test_missing_key_fails_before_client_call(operation: str) -> None:
    """A missing key never invokes the injected SDK. Author: 2692341798."""
    client = FakeClient([completion("unused")])
    instance = DeepSeekProvider(settings(key=None), client=client)

    with pytest.raises(AppError) as raised:
        if operation == "chat":
            await instance.generate_chat(message="hello", history=[])
        else:
            await instance.generate_advice(logs=[])

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_NOT_CONFIGURED
    assert client.chat.completions.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_factory", "expected_code", "attempts"),
    [
        (
            lambda: APIConnectionError(
                request=httpx.Request("POST", "https://provider.invalid")
            ),
            ErrorCode.AI_PROVIDER_UNAVAILABLE,
            3,
        ),
        (
            lambda: APITimeoutError(httpx.Request("POST", "https://provider.invalid")),
            ErrorCode.AI_PROVIDER_TIMEOUT,
            3,
        ),
        (lambda: status_error(429), ErrorCode.AI_RATE_LIMITED, 3),
        (lambda: status_error(400), ErrorCode.AI_PROVIDER_REQUEST_REJECTED, 1),
        (lambda: status_error(422), ErrorCode.AI_PROVIDER_REQUEST_REJECTED, 1),
        (lambda: status_error(401), ErrorCode.AI_PROVIDER_AUTH_FAILED, 1),
        (lambda: status_error(402), ErrorCode.AI_PROVIDER_QUOTA_EXHAUSTED, 1),
        (lambda: status_error(500), ErrorCode.AI_PROVIDER_UNAVAILABLE, 3),
        (lambda: status_error(503), ErrorCode.AI_PROVIDER_UNAVAILABLE, 3),
    ],
)
async def test_errors_are_mapped_with_bounded_attempts(
    error_factory: Callable[[], BaseException], expected_code: ErrorCode, attempts: int
) -> None:
    """Transport failures have stable mappings and attempt counts. Author: 2692341798."""
    errors = [error_factory() for _ in range(attempts)]
    instance, client, _ = provider(errors)

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is expected_code
    assert raised.value.status_code in {429, 502, 503, 504}
    assert len(client.chat.completions.calls) == attempts


@pytest.mark.asyncio
@pytest.mark.parametrize("retries", [0, 1, 3])
async def test_configured_retry_count_means_n_plus_one_total_attempts(retries: int) -> None:
    """Configured retry N permits exactly N plus one attempts. Author: 2692341798."""
    errors = [status_error(503) for _ in range(retries + 1)]
    instance, client, _ = provider(errors, retries=retries)

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_UNAVAILABLE
    assert len(client.chat.completions.calls) == retries + 1


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "", "   ", 123])
async def test_chat_rejects_empty_or_non_string_content(content: object) -> None:
    """Chat rejects unusable content without regeneration. Author: 2692341798."""
    instance, client, _ = provider([completion(content)])

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is ErrorCode.AI_INVALID_RESPONSE
    assert len(client.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_chat_rejects_truncated_content() -> None:
    """A truncated chat response is invalid. Author: 2692341798."""
    instance, _, _ = provider([completion("partial", finish_reason="length")])

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is ErrorCode.AI_INVALID_RESPONSE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[], model="served-model", usage=None),
        completion("valid", model=""),
        completion("valid", model=123),
        completion("partial", finish_reason="length"),
    ],
)
async def test_chat_parse_failures_are_logged_without_private_content(
    response: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid chat responses emit one redacted failure event. Author: 2692341798."""
    logger = logging.getLogger("wellness_app")
    old_propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.INFO, logger="wellness_app")
    instance, _, clock = provider([response])
    clock.now = 0.125
    try:
        with pytest.raises(AppError) as raised:
            await instance.generate_chat(message="PRIVATE-CHAT-INPUT", history=[])
    finally:
        logger.propagate = old_propagate

    assert raised.value.error_code is ErrorCode.AI_INVALID_RESPONSE
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.status == ErrorCode.AI_INVALID_RESPONSE.value
    assert record.retry_count == 0
    assert record.model == "deepseek-v4-flash"
    assert record.latency_ms == 0
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert "PRIVATE-CHAT-INPUT" not in record.getMessage()
    assert "partial" not in record.getMessage()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first",
    [
        completion(""),
        completion("partial", finish_reason="length"),
        completion("not-json"),
        completion('{"adviceText":"ok","extra":true}'),
        completion('{"wrong":"schema"}'),
    ],
)
async def test_advice_regenerates_invalid_output_once(first: object) -> None:
    """Invalid structured output gets one bounded regeneration. Author: 2692341798."""
    instance, client, _ = provider([first, completion('{"adviceText":"Recovered"}')])

    result = await instance.generate_advice(logs=[])

    assert result.advice_text == "Recovered"
    assert len(client.chat.completions.calls) == 2


@pytest.mark.asyncio
async def test_advice_repeated_invalid_output_fails_after_two_generations() -> None:
    """Repeated invalid JSON maps to invalid response. Author: 2692341798."""
    instance, client, _ = provider([completion("bad"), completion("still bad")])

    with pytest.raises(AppError) as raised:
        await instance.generate_advice(logs=[])

    assert raised.value.error_code is ErrorCode.AI_INVALID_RESPONSE
    assert len(client.chat.completions.calls) == 2


@pytest.mark.asyncio
async def test_advice_regeneration_shares_total_transport_attempt_budget() -> None:
    """Regeneration does not multiply the operation attempt budget. Author: 2692341798."""
    outcomes = [completion("bad"), status_error(503), status_error(503)]
    instance, client, _ = provider(outcomes, retries=2)

    with pytest.raises(AppError) as raised:
        await instance.generate_advice(logs=[])

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_UNAVAILABLE
    assert len(client.chat.completions.calls) == 3


@pytest.mark.asyncio
async def test_retry_backoff_is_exponential_with_jitter() -> None:
    """Retries use deterministic exponential backoff and jitter. Author: 2692341798."""
    outcomes = [status_error(503), status_error(503), completion("ok")]
    instance, _, clock = provider(outcomes, random=lambda: 0.25)

    await instance.generate_chat(message="hello", history=[])

    assert clock.sleeps == [pytest.approx(0.75), pytest.approx(1.25)]


@pytest.mark.asyncio
async def test_valid_retry_after_is_honored_inside_deadline() -> None:
    """A valid Retry-After controls the delay within budget. Author: 2692341798."""
    instance, client, clock = provider(
        [status_error(429, "2.5"), completion("ok")], timeout=4
    )

    await instance.generate_chat(message="hello", history=[])

    assert clock.sleeps == [2.5]
    assert client.chat.completions.calls[1]["timeout"] == 1.5


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after", ["invalid", "-1", "5"])
async def test_invalid_or_over_budget_retry_after_uses_backoff(retry_after: str) -> None:
    """Invalid or unaffordable Retry-After falls back safely. Author: 2692341798."""
    instance, _, clock = provider(
        [status_error(429, retry_after), completion("ok")], timeout=2
    )

    await instance.generate_chat(message="hello", history=[])

    assert clock.sleeps == [0.5]


@pytest.mark.asyncio
async def test_backoff_plus_jitter_is_clamped_to_remaining_budget() -> None:
    """Backoff and jitter cannot sleep beyond the deadline. Author: 2692341798."""
    instance, client, clock = provider(
        [status_error(503), completion("must not run")],
        retries=1,
        timeout=1,
        random=lambda: 10.0,
    )

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_TIMEOUT
    assert clock.sleeps == [1.0]
    assert len(client.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_deadline_exhaustion_stops_before_another_sdk_call() -> None:
    """Backoff consumption cannot exceed the absolute deadline. Author: 2692341798."""
    clock = FakeClock()

    async def exhaust_budget(_: float) -> None:
        clock.now = 1.0

    client = FakeClient([status_error(503), completion("must not run")])
    instance = DeepSeekProvider(
        settings(timeout=1),
        client=client,
        sleep=exhaust_budget,
        random=lambda: 0.0,
        clock=clock,
    )

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_TIMEOUT
    assert len(client.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_hard_deadline_cancels_sdk_coroutine_and_maps_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The adapter enforces its deadline around a hanging SDK call. Author: 2692341798."""
    completions = HangingCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    configured = settings().model_copy(update={"deepseek_timeout_seconds": 0.01})
    instance = DeepSeekProvider(configured, client=client)
    logger = logging.getLogger("wellness_app")
    old_propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.INFO, logger="wellness_app")
    try:
        with pytest.raises(AppError) as raised:
            await asyncio.wait_for(
                instance.generate_chat(message="PRIVATE-HANGING-INPUT", history=[]),
                timeout=0.1,
            )
    finally:
        logger.propagate = old_propagate

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_TIMEOUT
    assert len(completions.calls) == 1
    assert completions.cancelled is True
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.status == ErrorCode.AI_PROVIDER_TIMEOUT.value
    assert record.retry_count == 0
    assert record.model == "deepseek-v4-flash"
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert "PRIVATE-HANGING-INPUT" not in record.getMessage()


@pytest.mark.asyncio
async def test_sdk_response_validation_error_is_invalid_and_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SDK validation failures are non-retryable and safely logged. Author: 2692341798."""
    request = httpx.Request("POST", "https://provider.invalid")
    response = httpx.Response(
        200,
        request=request,
        json={"content": "PRIVATE-PROVIDER-CONTENT"},
    )
    error = APIResponseValidationError(
        response=response,
        body={"content": "PRIVATE-PROVIDER-CONTENT"},
        message="PRIVATE-VALIDATION-DETAIL",
    )
    logger = logging.getLogger("wellness_app")
    old_propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.INFO, logger="wellness_app")
    instance, client, _ = provider([error])
    try:
        with pytest.raises(AppError) as raised:
            await instance.generate_chat(message="PRIVATE-INPUT", history=[])
    finally:
        logger.propagate = old_propagate

    assert raised.value.error_code is ErrorCode.AI_INVALID_RESPONSE
    assert len(client.chat.completions.calls) == 1
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.status == ErrorCode.AI_INVALID_RESPONSE.value
    assert record.retry_count == 0
    assert record.model == "deepseek-v4-flash"
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    rendered = record.getMessage()
    for private in (
        "PRIVATE-PROVIDER-CONTENT",
        "PRIVATE-VALIDATION-DETAIL",
        "PRIVATE-INPUT",
    ):
        assert private not in rendered


@pytest.mark.asyncio
async def test_response_arriving_after_absolute_deadline_is_rejected() -> None:
    """A late SDK response cannot escape the operation deadline. Author: 2692341798."""
    clock = FakeClock()

    def late_response() -> object:
        """Advance beyond the deadline before responding. Author: 2692341798."""
        clock.now = 1.1
        return completion("late")

    instance, client, _ = provider([late_response], timeout=1, clock=clock)

    with pytest.raises(AppError) as raised:
        await instance.generate_chat(message="hello", history=[])

    assert raised.value.error_code is ErrorCode.AI_PROVIDER_TIMEOUT
    assert len(client.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_logs_are_allowlisted_and_redacted(caplog: pytest.LogCaptureFixture) -> None:
    """Provider observability never records private payloads. Author: 2692341798."""
    logger = logging.getLogger("wellness_app")
    old_propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.INFO, logger="wellness_app")
    secret_message = "PRIVATE-MESSAGE-CONTENT"
    secret_output = "PRIVATE-GENERATED-CONTENT"
    instance, _, _ = provider([completion(secret_output)])
    try:
        await instance.generate_chat(message=secret_message, history=[])
    finally:
        logger.propagate = old_propagate

    assert caplog.records
    record = caplog.records[-1]
    assert record.event == "ai_provider_call"
    assert record.status == "success"
    assert record.model == "served-model"
    assert record.retry_count == 0
    assert record.latency_ms == 0
    assert record.prompt_tokens == 11
    assert record.completion_tokens == 7
    rendered = " ".join(record.getMessage() for record in caplog.records)
    assert secret_message not in rendered
    assert secret_output not in rendered
    for forbidden in ("messages", "prompt", "output", "headers", "exception"):
        assert not hasattr(record, forbidden)


@pytest.mark.asyncio
async def test_failed_transport_log_is_allowlisted_and_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Final transport failure records metrics but no provider details. Author: 2692341798."""
    request = httpx.Request("POST", "https://provider.invalid")
    response = httpx.Response(
        503,
        request=request,
        headers={"X-Secret": "PRIVATE-HEADER"},
        json={"detail": "PRIVATE-BODY"},
    )
    errors = [
        APIStatusError("PRIVATE-EXCEPTION", response=response, body={"secret": "PRIVATE-BODY"})
        for _ in range(3)
    ]
    logger = logging.getLogger("wellness_app")
    old_propagate = logger.propagate
    logger.propagate = True
    caplog.set_level(logging.INFO, logger="wellness_app")
    instance, _, clock = provider(errors)
    try:
        with pytest.raises(AppError):
            await instance.generate_chat(message="PRIVATE-INPUT", history=[])
    finally:
        logger.propagate = old_propagate

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.status == 503
    assert record.retry_count == 2
    assert record.model == "deepseek-v4-flash"
    assert record.latency_ms == round(clock.now * 1000)
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    rendered = record.getMessage()
    for private in ("PRIVATE-EXCEPTION", "PRIVATE-HEADER", "PRIVATE-BODY", "PRIVATE-INPUT"):
        assert private not in rendered


def test_default_client_is_constructed_only_for_provider_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify default SDK construction occurs at provider instantiation.

    Author: 2692341798
    """
    calls: list[dict[str, Any]] = []
    fake_client = FakeClient([completion("unused")])

    def fake_async_openai(**kwargs: Any) -> FakeClient:
        """Capture SDK construction without network access. Author: 2692341798."""
        calls.append(kwargs)
        return fake_client

    monkeypatch.setattr(deepseek_module, "AsyncOpenAI", fake_async_openai)
    assert calls == []

    configured = Settings(
        _env_file=None,
        DEEPSEEK_API_KEY="configured-key",
        DEEPSEEK_BASE_URL="https://custom.deepseek.invalid",
        DEEPSEEK_TIMEOUT_SECONDS=12,
    )
    DeepSeekProvider(configured)

    assert calls == [
        {
            "api_key": "configured-key",
            "base_url": "https://custom.deepseek.invalid",
            "timeout": 12.0,
            "max_retries": 0,
        }
    ]
