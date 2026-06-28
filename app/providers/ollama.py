import asyncio
import json
import logging
import random as random_module
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import log_event
from app.prompts.advice import ADVICE_SYSTEM_PROMPT
from app.prompts.chat import CHAT_SYSTEM_PROMPT
from app.schemas.advice import AdvicePayload, AdviceProviderResult, WellnessLog
from app.schemas.chat import ChatProviderResult, HistoryItem

try:  # pragma: no cover - optional dependency
    from ollama import Client as OllamaClient
except ImportError:  # pragma: no cover - optional dependency
    OllamaClient = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore[assignment]

_LOGGER = logging.getLogger("wellness_app")
_BACKOFF_BASE_SECONDS = 0.5


class _ChatClient(Protocol):
    def chat(self, **kwargs: Any) -> Any: ...


@dataclass(slots=True)
class _Operation:
    deadline: float
    max_attempts: int
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class _ParsedResponse:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


class OllamaProvider:
    """Local Ollama-backed provider for wellness chat and advice. Author: 2692341798."""

    def __init__(
        self,
        settings: Settings,
        client: _ChatClient | None = None,
        embedder: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random: Callable[[], float] = random_module.random,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize local model clients and the optional embedding model. Author: 2692341798."""
        self._settings = settings
        self._sleep = sleep
        self._random = random
        self._clock = clock
        self._embedder = embedder or self._build_embedder()
        self._client = client or self._build_client()

    def _build_embedder(self) -> Any | None:
        if SentenceTransformer is None:
            return None
        try:
            return SentenceTransformer(self._settings.embed_model)
        except Exception:
            return None

    def _build_client(self) -> _ChatClient | None:
        if OllamaClient is None:
            return None
        try:
            return OllamaClient(host=self._settings.ollama_host)
        except Exception:
            return None

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
        response = await self._request(operation, messages=messages)
        try:
            parsed = self._parse_completion(response)
        except AppError as error:
            self._log_failure(operation, error.error_code.value, self._settings.chat_model)
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
            response = await self._request(operation, messages=messages, json_mode=True)
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
        self._log_failure(operation, error.error_code.value, self._settings.chat_model)
        raise error

    def _require_configured(self) -> None:
        if self._client is None:
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
        messages: list[dict[str, str]],
        json_mode: bool = False,
    ) -> Any:
        while operation.attempts < operation.max_attempts:
            remaining = operation.deadline - self._clock()
            if remaining <= 0:
                error = AppError.provider_timeout()
                self._log_failure(operation, error.error_code.value, self._settings.chat_model)
                raise error
            operation.attempts += 1
            kwargs: dict[str, Any] = {
                "model": self._settings.chat_model,
                "messages": messages,
                "stream": False,
            }
            if json_mode:
                kwargs["format"] = "json"
            try:
                async with asyncio.timeout(remaining):
                    response = self._client.chat(**kwargs)  # type: ignore[union-attr]
                if self._clock() >= operation.deadline:
                    error = AppError.provider_timeout()
                    self._log_failure(operation, error.error_code.value, self._settings.chat_model)
                    raise error
                return response
            except TimeoutError:
                error = AppError.provider_timeout()
                self._log_failure(operation, error.error_code.value, self._settings.chat_model)
                raise error from None
            except Exception as exc:
                mapped = self._map_error(exc)
                if not self._is_retryable(exc) or operation.attempts >= operation.max_attempts:
                    self._log_failure(
                        operation, self._status(exc, mapped), self._settings.chat_model
                    )
                    raise mapped from None
                delay = self._retry_delay(exc, operation.attempts - 1, operation.deadline)
                await self._sleep(delay)

        error = AppError.provider_timeout()
        self._log_failure(operation, error.error_code.value, self._settings.chat_model)
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
        if not hasattr(exc, "response"):
            return None
        response = getattr(exc, "response", None)
        if response is None:
            return None
        headers = getattr(response, "headers", None)
        if not isinstance(headers, dict):
            return None
        value = headers.get("Retry-After")
        if not isinstance(value, str):
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        if isinstance(exc, TimeoutError | ConnectionError):
            return True
        return isinstance(exc, RuntimeError) and "connection" in str(exc).lower()

    @staticmethod
    def _map_error(exc: BaseException) -> AppError:
        if isinstance(exc, TimeoutError):
            return AppError.provider_timeout()
        if isinstance(exc, ConnectionError):
            return AppError.provider_unavailable()
        return AppError.provider_unavailable()

    @staticmethod
    def _status(exc: BaseException, mapped: AppError) -> int | str:
        return mapped.error_code.value

    @staticmethod
    def _parse_completion(response: Any) -> _ParsedResponse:
        message = OllamaProvider._response_value(response, "message")
        if message is None:
            raise AppError.invalid_response()

        content = OllamaProvider._response_value(message, "content")
        model = OllamaProvider._response_value(response, "model")
        if not isinstance(content, str) or not content.strip():
            raise AppError.invalid_response()
        if not isinstance(model, str) or not model.strip():
            model = "llama3.1"
        prompt_tokens = OllamaProvider._response_value(response, "prompt_eval_count")
        completion_tokens = OllamaProvider._response_value(response, "eval_count")
        return _ParsedResponse(
            content=content.strip(),
            model=model,
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=(
                completion_tokens if isinstance(completion_tokens, int) else None
            ),
        )

    @staticmethod
    def _response_value(response: Any, key: str) -> Any:
        if isinstance(response, dict):
            return response.get(key)
        if hasattr(response, key):
            return getattr(response, key)
        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
            if isinstance(dumped, dict):
                return dumped.get(key)
        return None

    def _log_success(self, operation: _Operation, parsed: _ParsedResponse) -> None:
        log_event(
            _LOGGER,
            "ai_provider_call",
            status="success",
            latency_ms=round(
                (self._settings.deepseek_timeout_seconds)
                * 1000,
                3,
            ),
            model=parsed.model,
            attempt=operation.attempts,
        )

    def _log_failure(self, operation: _Operation, status: int | str, model: str) -> None:
        log_event(
            _LOGGER,
            "ai_provider_call",
            status="failure",
            latency_ms=round(
                (self._settings.deepseek_timeout_seconds)
                * 1000,
                3,
            ),
            model=model,
            attempt=operation.attempts,
            error_code=status,
        )
