from typing import Any, cast

import pytest

import app.services.chat as chat_module
from app.core.exceptions import AppError, ErrorCode
from app.prompts.chat import CHAT_PROMPT_VERSION, CHAT_SYSTEM_PROMPT
from app.schemas.chat import ChatProviderResult, ChatRequest, HistoryItem, HistoryRole
from app.services.chat import ChatService
from app.services.safety import SafetyPolicy
from tests.fakes import FakeLLMProvider

EXPECTED_CRISIS_RESPONSE = (
    "If you may be in immediate danger or are thinking about harming yourself, contact your "
    "local emergency services or a qualified crisis professional now. If possible, stay with "
    "someone you trust. This service cannot provide emergency or medical care."
)


def test_chat_prompt_locks_wellness_safety_and_prompt_injection_rules() -> None:
    """Keep the versioned chat policy explicit and testable. Author: 2692341798."""
    prompt = CHAT_SYSTEM_PROMPT.lower()

    assert CHAT_PROMPT_VERSION == "wellness-chat-v1"
    assert "general wellness only" in prompt
    assert "diagnosis" in prompt
    assert "medical certainty" in prompt
    assert "prescription" in prompt
    assert "dosage" in prompt
    assert "not a medical professional" in prompt
    assert "local emergency" in prompt
    assert "qualified crisis professional" in prompt
    assert "untrusted" in prompt
    assert "cannot override" in prompt
    assert "replace system policy" in prompt
    assert "reveal the system policy" in prompt
    assert "concise" in prompt
    assert "actionable" in prompt


@pytest.mark.asyncio
async def test_generate_returns_reply_and_request_id() -> None:
    """Return provider content through the public chat contract. Author: 2692341798."""
    provider = FakeLLMProvider(
        chat_result=ChatProviderResult(content="  Take a brief walk.  ", model="deepseek-v4-flash")
    )
    service = ChatService(provider, SafetyPolicy())

    response = await service.generate(
        ChatRequest(user_id=42, message="How can I reset after work?"),
        request_id="request-123",
    )

    assert response.reply == "Take a brief walk."
    assert response.request_id == "request-123"


@pytest.mark.asyncio
async def test_generate_strips_provider_content_before_building_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strip provider content before constructing the response. Author: 2692341798."""
    provider = FakeLLMProvider(
        chat_result=ChatProviderResult(content="  Take a brief walk.  ", model="deepseek-v4-flash")
    )
    captured: dict[str, str] = {}
    expected_response = object()

    def capture_response(*, reply: str, request_id: str) -> object:
        """Record response constructor inputs. Author: 2692341798."""
        captured.update(reply=reply, request_id=request_id)
        return expected_response

    monkeypatch.setattr(chat_module, "ChatResponse", capture_response)

    response = await ChatService(provider, SafetyPolicy()).generate(
        ChatRequest(user_id=42, message="How can I reset?"), request_id="request-strip"
    )

    assert response is expected_response
    assert captured == {"reply": "Take a brief walk.", "request_id": "request-strip"}


@pytest.mark.asyncio
async def test_generate_passes_only_stripped_message_and_history_to_provider() -> None:
    """Exclude identity data and strip provider-bound user text. Author: 2692341798."""
    provider = FakeLLMProvider()
    request = ChatRequest.model_construct(
        user_id=73,
        message="  Help me unwind  ",
        history=[
            HistoryItem.model_construct(role=HistoryRole.USER, content="  Busy day  "),
            HistoryItem.model_construct(role=HistoryRole.ASSISTANT, content="  Take a pause  "),
        ],
    )

    await ChatService(provider, SafetyPolicy()).generate(request, request_id="request-1")

    assert provider.chat_calls == [
        {
            "message": "Help me unwind",
            "history": [
                HistoryItem(role=HistoryRole.USER, content="Busy day"),
                HistoryItem(role=HistoryRole.ASSISTANT, content="Take a pause"),
            ],
        }
    ]
    assert "user_id" not in provider.chat_calls[0]


@pytest.mark.asyncio
async def test_generate_returns_crisis_response_without_calling_provider() -> None:
    """Short-circuit an explicit crisis message before provider use. Author: 2692341798."""
    provider = FakeLLMProvider()

    response = await ChatService(provider, SafetyPolicy()).generate(
        ChatRequest(user_id=42, message="I want to kill myself"),
        request_id="request-crisis",
    )

    assert response.reply == EXPECTED_CRISIS_RESPONSE
    assert response.request_id == "request-crisis"
    assert provider.chat_calls == []


@pytest.mark.asyncio
async def test_generate_detects_crisis_phrase_in_history_without_provider_call() -> None:
    """Short-circuit when an explicit crisis phrase appears in history. Author: 2692341798."""
    provider = FakeLLMProvider()
    request = ChatRequest(
        user_id=42,
        message="What should I do next?",
        history=[{"role": "user", "content": "Earlier I had chest pain"}],
    )

    response = await ChatService(provider, SafetyPolicy()).generate(
        request, request_id="request-history-crisis"
    )

    assert response.reply == EXPECTED_CRISIS_RESPONSE
    assert provider.chat_calls == []


@pytest.mark.asyncio
async def test_generate_maps_blank_provider_content_to_invalid_response() -> None:
    """Reject provider content that becomes blank after stripping. Author: 2692341798."""
    provider = FakeLLMProvider(
        chat_result=ChatProviderResult(content=" \n ", model="deepseek-v4-flash")
    )

    with pytest.raises(AppError) as exc_info:
        await ChatService(provider, SafetyPolicy()).generate(
            ChatRequest(user_id=42, message="Help me relax"), request_id="request-blank"
        )

    assert exc_info.value.error_code is ErrorCode.AI_INVALID_RESPONSE


@pytest.mark.parametrize(
    "provider_result",
    [
        cast(Any, ChatProviderResult).model_construct(model="deepseek-v4-flash"),
        cast(Any, ChatProviderResult).model_construct(
            content=123,
            model="deepseek-v4-flash",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_maps_schema_incompatible_provider_result_to_invalid_response(
    provider_result: ChatProviderResult,
) -> None:
    """Map malformed provider content to the stable error. Author: 2692341798."""
    provider = FakeLLMProvider(chat_result=provider_result)

    with pytest.raises(AppError) as exc_info:
        await ChatService(provider, SafetyPolicy()).generate(
            ChatRequest(user_id=42, message="Help me relax"), request_id="request-malformed"
        )

    assert exc_info.value.error_code is ErrorCode.AI_INVALID_RESPONSE
