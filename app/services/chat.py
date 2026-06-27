from app.core.exceptions import AppError
from app.providers.base import LLMProvider
from app.schemas.chat import ChatProviderResult, ChatRequest, ChatResponse, HistoryItem
from app.services.safety import SafetyPolicy


class ChatService:
    """Coordinate deterministic safety and provider-backed chat. Author: 2692341798."""

    def __init__(self, provider: LLMProvider, safety_policy: SafetyPolicy) -> None:
        """Store provider-independent chat collaborators. Author: 2692341798."""
        self._provider = provider
        self._safety_policy = safety_policy

    async def generate(self, request: ChatRequest, request_id: str) -> ChatResponse:
        """Generate a safe wellness reply for a validated request. Author: 2692341798."""
        crisis_response = self._safety_policy.evaluate(
            [request.message, *(item.content for item in request.history)]
        )
        if crisis_response is not None:
            return ChatResponse(reply=crisis_response, request_id=request_id)

        stripped_history = [
            HistoryItem(role=item.role, content=item.content.strip()) for item in request.history
        ]
        result = await self._provider.generate_chat(
            message=request.message.strip(),
            history=stripped_history,
        )
        if not isinstance(result, ChatProviderResult):
            raise AppError.invalid_response()

        raw_content = getattr(result, "content", None)
        if not isinstance(raw_content, str):
            raise AppError.invalid_response()

        reply = raw_content.strip()
        if not reply:
            raise AppError.invalid_response()

        return ChatResponse(reply=reply, request_id=request_id)
