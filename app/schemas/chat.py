from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HistoryRole(StrEnum):
    """Allowed roles in caller-supplied chat history. Author: 2692341798."""

    USER = "user"
    ASSISTANT = "assistant"


class HistoryItem(BaseModel):
    """One bounded caller-supplied chat history item. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    role: HistoryRole
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content", mode="before")
    @classmethod
    def _strip_content(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatRequest(BaseModel):
    """Validated request contract for wellness chat. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId", gt=0, strict=True)
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)

    @field_validator("message", mode="before")
    @classmethod
    def _strip_message(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_aggregate_text_length(self) -> Self:
        aggregate_length = len(self.message) + sum(len(item.content) for item in self.history)
        if aggregate_length > 20_000:
            raise ValueError("message and history content must total at most 20000 characters")
        return self


class ChatResponse(BaseModel):
    """Public response contract for wellness chat. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    reply: str = Field(min_length=1)
    request_id: str = Field(alias="requestId")

    @field_validator("reply", mode="before")
    @classmethod
    def _strip_reply(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatProviderResult(BaseModel):
    """Provider-independent chat generation result. Author: 2692341798."""

    model_config = ConfigDict(populate_by_name=True)

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
