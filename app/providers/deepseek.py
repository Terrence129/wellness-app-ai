import asyncio
import json
import logging
import random as random_module
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import log_event
from app.prompts.advice import ADVICE_SYSTEM_PROMPT
from app.prompts.chat import CHAT_SYSTEM_PROMPT
from app.schemas.advice import AdvicePayload, AdviceProviderResult, WellnessLog
from app.schemas.chat import ChatProviderResult, HistoryItem

_LOGGER = logging.getLogger("wellness_app")
_THINKING_DISABLED = {"thinking": {"type": "disabled"}}
_RETRYABLE_STATUSES = frozenset({429, 500, 503})
_TRUNCATED_FINISH_REASONS = frozenset({"length"})
_BACKOFF_BASE_SECONDS = 0.5


class _Completions(Protocol):
    async def create(self, **kwargs: Any) -> object: ...


class _Chat(Protocol):
    completions: _Completions


class _Client(Protocol):
    chat: _Chat


@dataclass(slots=True)
class _Operation:
    deadline: float
    max_attempts: int
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class _ParsedCompletion:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


class DeepSeekProvider:
    """Bounded OpenAI-compatible adapter for DeepSeek. Author: 2692341798."""

    def __init__(
        self,
        settings: Settings,
        client: _Client | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random: Callable[[], float] = random_module.random,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build an adapter with injectable I/O and timing. Author: 2692341798."""
        self._settings = settings
        self._sleep = sleep
        self._random = random
        self._clock = clock
        if client is not None:
            self._client: _Client | None = client
        elif settings.deepseek_api_key is not None:
            self._client = cast(
                _Client,
                AsyncOpenAI(
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url,
                    timeout=settings.deepseek_timeout_seconds,
                    max_retries=0,
                ),
            )
        else:
            self._client = None

    async def generate_chat(
        self, *, message: str, history: Sequence[HistoryItem]
    ) -> ChatProviderResult:
        """Generate and validate one wellness-chat response. Author: 2692341798."""
        self._require_configured()
        operation = self._new_operation()
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
        messages.extend(
            {"role": item.role.value, "content": item.content} for item in history
        )
        messages.append({"role": "user", "content": message})
        response = await self._request(
            operation,
            model=self._settings.deepseek_chat_model,
            messages=messages,
        )
        try:
            parsed = self._parse_completion(response)
        except AppError as error:
            self._log_failure(
                operation,
                error.error_code.value,
                self._settings.deepseek_chat_model,
            )
            raise
        self._log_success(operation, parsed)
        return ChatProviderResult(
            content=parsed.content,
            model=parsed.model,
            prompt_tokens=parsed.prompt_tokens,
            completion_tokens=parsed.completion_tokens,
        )

    async def generate_advice(
        self, *, logs: Sequence[WellnessLog]
    ) -> AdviceProviderResult:
        """Generate and validate strict JSON wellness advice. Author: 2692341798."""
        self._require_configured()
        operation = self._new_operation()
        serialized_logs = [
            log.model_dump(mode="json", by_alias=True) for log in logs
        ]
        messages = [
            {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"logs": serialized_logs}, separators=(",", ":"), ensure_ascii=True
                ),
            },
        ]

        for generation in range(2):
            if operation.attempts >= operation.max_attempts:
                break
            response = await self._request(
                operation,
                model=self._settings.deepseek_advice_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            try:
                parsed = self._parse_completion(response)
                payload = AdvicePayload.model_validate_json(parsed.content)
            except (AppError, ValidationError, ValueError, TypeError, json.JSONDecodeError):
                if generation == 0 and operation.attempts < operation.max_attempts:
                    continue
                break
            self._log_success(operation, parsed)
            return AdviceProviderResult(
                advice_text=payload.advice_text,
                model=parsed.model,
                prompt_tokens=parsed.prompt_tokens,
                completion_tokens=parsed.completion_tokens,
            )

        error = AppError.invalid_response()
        self._log_failure(operation, error.error_code.value, self._settings.deepseek_advice_model)
        raise error

    def _require_configured(self) -> None:
        if self._settings.deepseek_api_key is None or self._client is None:
            raise AppError.provider_not_configured()

    def _new_operation(self) -> _Operation:
        return _Operation(
            deadline=self._clock() + self._settings.deepseek_timeout_seconds,
            max_attempts=self._settings.deepseek_max_retries + 1,
        )

    async def _request(
        self,
        operation: _Operation,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> object:
        while operation.attempts < operation.max_attempts:
            remaining = operation.deadline - self._clock()
            if remaining <= 0:
                error = AppError.provider_timeout()
                self._log_failure(operation, error.error_code.value, model)
                raise error
            operation.attempts += 1
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "extra_body": _THINKING_DISABLED,
                "stream": False,
                "timeout": remaining,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            try:
                client = cast(_Client, self._client)
                async with asyncio.timeout(remaining):
                    response = await client.chat.completions.create(**kwargs)
                if self._clock() >= operation.deadline:
                    error = AppError.provider_timeout()
                    self._log_failure(operation, error.error_code.value, model)
                    raise error
                return response
            except TimeoutError:
                error = AppError.provider_timeout()
                self._log_failure(operation, error.error_code.value, model)
                raise error from None
            except APIResponseValidationError:
                error = AppError.invalid_response()
                self._log_failure(operation, error.error_code.value, model)
                raise error from None
            except (APITimeoutError, APIConnectionError, APIStatusError) as exc:
                mapped = self._map_error(exc)
                if not self._is_retryable(exc) or operation.attempts >= operation.max_attempts:
                    self._log_failure(operation, self._status(exc, mapped), model)
                    raise mapped from None
                delay = self._retry_delay(exc, operation.attempts - 1, operation.deadline)
                await self._sleep(delay)

        error = AppError.provider_timeout()
        self._log_failure(operation, error.error_code.value, model)
        raise error

    def _retry_delay(self, exc: BaseException, retry: int, deadline: float) -> float:
        remaining = max(0.0, deadline - self._clock())
        retry_after = self._retry_after(exc)
        if retry_after is not None and retry_after < remaining:
            return retry_after
        return min(
            _BACKOFF_BASE_SECONDS * (2.0**retry) + self._random(),
            remaining,
        )

    @staticmethod
    def _retry_after(exc: BaseException) -> float | None:
        if not isinstance(exc, APIStatusError):
            return None
        value = exc.response.headers.get("Retry-After")
        if not isinstance(value, str):
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        if isinstance(exc, (APITimeoutError, APIConnectionError)):
            return True
        return isinstance(exc, APIStatusError) and exc.status_code in _RETRYABLE_STATUSES

    @staticmethod
    def _map_error(exc: BaseException) -> AppError:
        if isinstance(exc, APITimeoutError):
            return AppError.provider_timeout()
        if isinstance(exc, APIConnectionError):
            return AppError.provider_unavailable()
        if isinstance(exc, APIStatusError):
            if exc.status_code == 429:
                return AppError.rate_limited()
            if exc.status_code in {400, 422}:
                return AppError.provider_request_rejected()
            if exc.status_code == 401:
                return AppError.provider_auth_failed()
            if exc.status_code == 402:
                return AppError.provider_quota_exhausted()
        return AppError.provider_unavailable()

    @staticmethod
    def _status(exc: BaseException, mapped: AppError) -> int | str:
        if isinstance(exc, APIStatusError):
            return exc.status_code
        return mapped.error_code.value

    @staticmethod
    def _parse_completion(response: object) -> _ParsedCompletion:
        choices = getattr(response, "choices", None)
        if not isinstance(choices, list) or not choices:
            raise AppError.invalid_response()
        choice = choices[0]
        if getattr(choice, "finish_reason", None) in _TRUNCATED_FINISH_REASONS:
            raise AppError.invalid_response()
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        model = getattr(response, "model", None)
        if not isinstance(content, str) or not content.strip():
            raise AppError.invalid_response()
        if not isinstance(model, str) or not model.strip():
            raise AppError.invalid_response()
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        return _ParsedCompletion(
            content=content.strip(),
            model=model,
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=(
                completion_tokens if isinstance(completion_tokens, int) else None
            ),
        )

    def _log_success(self, operation: _Operation, parsed: _ParsedCompletion) -> None:
        log_event(
            _LOGGER,
            "ai_provider_call",
            status="success",
            latency_ms=round(
                (self._settings.deepseek_timeout_seconds
                 - max(0.0, operation.deadline - self._clock()))
                * 1000
            ),
            model=parsed.model,
            retry_count=max(0, operation.attempts - 1),
            prompt_tokens=parsed.prompt_tokens,
            completion_tokens=parsed.completion_tokens,
        )

    def _log_failure(self, operation: _Operation, status: int | str, model: str) -> None:
        log_event(
            _LOGGER,
            "ai_provider_call",
            status=status,
            latency_ms=round(
                (self._settings.deepseek_timeout_seconds
                 - max(0.0, operation.deadline - self._clock()))
                * 1000
            ),
            model=model,
            retry_count=max(0, operation.attempts - 1),
            prompt_tokens=None,
            completion_tokens=None,
        )
