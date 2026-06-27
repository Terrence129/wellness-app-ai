from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.core.logging import get_request_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    """Generate one general-wellness chat response. Author: 2692341798."""
    request_id = get_request_id()
    if request_id is None:
        raise RuntimeError("request ID context is unavailable")
    return await service.generate(request, request_id)
