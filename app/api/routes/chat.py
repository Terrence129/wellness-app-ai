from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.core.logging import get_request_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/ai", tags=["AI Chat"])


_CHAT_DESC = (
    "Generate a general-wellness chatbot response for the supplied message "
    "and bounded conversation history.\n\n"
    "The Spring Boot backend forwards the user's wellness question and "
    "at most 12 previous user/assistant turns. DeepSeek is stateless "
    "— Spring Boot owns persistence and submits history on every request.\n\n"
    "**Safety**: Before calling DeepSeek, a deterministic safety policy "
    "checks for explicit crisis language (e.g. self-harm, suicide). "
    "When matched, a fixed escalation message is returned without "
    "calling the provider. User text is treated as untrusted input.\n\n"
    "**Privacy**: The internal `userId` is never sent to DeepSeek. "
    "Messages, history, prompts, and generated text are excluded from logs."
)


@router.post(
    "/chat",
    response_model=ChatResponse,
    response_model_by_alias=True,
    summary="Wellness Chat",
    description=_CHAT_DESC,
)
async def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    """Generate one general-wellness chat response. Author: 2692341798."""
    request_id = get_request_id()
    if request_id is None:
        raise RuntimeError("request ID context is unavailable")
    return await service.generate(request, request_id)
