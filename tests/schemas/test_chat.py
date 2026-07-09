# Author: Huang Qijun
# Email: 2692341798@qq.com

import pytest
from pydantic import ValidationError

from app.schemas.chat import (
    ChatProviderResult,
    ChatRequest,
    ChatResponse,
    HistoryItem,
    HistoryRole,
)


def test_chat_request_strips_text_and_accepts_field_names() -> None:
    """Validate trimming and Python-name population. Author: 2692341798."""
    request = ChatRequest(
        user_id=1,
        message="  improve sleep  ",
        history=[HistoryItem(role=HistoryRole.USER, content="  hello  ")],
    )

    assert request.message == "improve sleep"
    assert request.history[0].content == "hello"


@pytest.mark.parametrize("message", ["x", "x" * 2000])
def test_chat_message_accepts_boundary_lengths(message: str) -> None:
    """Accept valid message length boundaries. Author: 2692341798."""
    assert ChatRequest(userId=1, message=message).message == message


@pytest.mark.parametrize("message", ["   ", "x" * 2001])
def test_chat_message_rejects_invalid_lengths(message: str) -> None:
    """Reject blank or oversized messages. Author: 2692341798."""
    with pytest.raises(ValidationError):
        ChatRequest(userId=1, message=message)


def test_chat_request_requires_positive_user_id() -> None:
    """Reject a non-positive user identifier. Author: 2692341798."""
    with pytest.raises(ValidationError):
        ChatRequest(userId=0, message="hello")


@pytest.mark.parametrize("user_id", [True, "1", 1.0])
def test_chat_request_rejects_non_strict_integer_user_id(user_id: object) -> None:
    """Reject coercible non-integer user identifiers. Author: 2692341798."""
    with pytest.raises(ValidationError):
        ChatRequest(userId=user_id, message="hello")


def test_chat_history_accepts_twelve_items_and_rejects_thirteen() -> None:
    """Enforce the bounded history size. Author: 2692341798."""
    item = {"role": "user", "content": "x"}

    assert len(ChatRequest(userId=1, message="x", history=[item] * 12).history) == 12
    with pytest.raises(ValidationError):
        ChatRequest(userId=1, message="x", history=[item] * 13)


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_history_accepts_supported_roles(role: str) -> None:
    """Accept only caller-safe conversation roles. Author: 2692341798."""
    assert HistoryItem(role=role, content="x").role.value == role


@pytest.mark.parametrize("role", ["system", "tool"])
def test_history_rejects_unsupported_roles(role: str) -> None:
    """Reject roles reserved for provider internals. Author: 2692341798."""
    with pytest.raises(ValidationError):
        HistoryItem(role=role, content="x")


@pytest.mark.parametrize("content", ["x", "x" * 4000])
def test_history_content_accepts_boundary_lengths(content: str) -> None:
    """Accept valid history content boundaries. Author: 2692341798."""
    assert HistoryItem(role="user", content=content).content == content


@pytest.mark.parametrize("content", ["   ", "x" * 4001])
def test_history_content_rejects_invalid_lengths(content: str) -> None:
    """Reject blank or oversized history content. Author: 2692341798."""
    with pytest.raises(ValidationError):
        HistoryItem(role="user", content=content)


def test_chat_request_accepts_aggregate_limit_and_rejects_excess() -> None:
    """Bound aggregate user-controlled text. Author: 2692341798."""
    accepted = ChatRequest(
        userId=1,
        message="m" * 2000,
        history=[{"role": "user", "content": "h" * 1500}] * 12,
    )

    assert len(accepted.message) + sum(len(item.content) for item in accepted.history) == 20000
    with pytest.raises(ValidationError):
        ChatRequest(
            userId=1,
            message="m" * 2000,
            history=[{"role": "user", "content": "h" * 1500}] * 11
            + [{"role": "assistant", "content": "h" * 1501}],
        )


def test_chat_models_serialize_camel_case_aliases() -> None:
    """Serialize public contracts with camel-case aliases. Author: 2692341798."""
    request = ChatRequest(user_id=7, message="hello")
    response = ChatResponse(reply="  hello back  ", request_id="request-1")

    assert request.model_dump(by_alias=True) == {"userId": 7, "message": "hello", "history": []}
    assert response.reply == "hello back"
    assert response.model_dump(by_alias=True) == {
        "reply": "hello back",
        "requestId": "request-1",
    }


def test_chat_response_rejects_blank_reply() -> None:
    """Reject an unusable provider-facing reply. Author: 2692341798."""
    with pytest.raises(ValidationError):
        ChatResponse(reply="  ", requestId="request-1")


def test_chat_provider_result_retains_usage() -> None:
    """Represent provider output and optional usage. Author: 2692341798."""
    result = ChatProviderResult(
        content="answer",
        model="deepseek-v4-flash",
        prompt_tokens=12,
        completion_tokens=None,
    )

    assert result.prompt_tokens == 12
    assert result.completion_tokens is None
