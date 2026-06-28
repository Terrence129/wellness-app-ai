
from app.core.exceptions import AppError
from app.prompts.chat import format_rag_context
from app.providers.base import LLMProvider
from app.rag.retriever import Retriever
from app.schemas.chat import ChatProviderResult, ChatRequest, ChatResponse, HistoryItem, HistoryRole
from app.services.safety import SafetyPolicy


class ChatService:
    """Coordinate deterministic safety, retrieval, and provider-backed chat. Author: 2692341798."""

    def __init__(
        self,
        provider: LLMProvider,
        safety_policy: SafetyPolicy,
        retriever: Retriever | None = None,
    ) -> None:
        """Store provider-independent chat collaborators. Author: 2692341798."""
        self._provider = provider
        self._safety_policy = safety_policy
        self._retriever = retriever

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

        knowledge_context = await self._retrieve_context(request.message, request.history)

        result = await self._provider.generate_chat(
            message=request.message.strip(),
            history=stripped_history,
            knowledge_context=knowledge_context,
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

    async def _retrieve_context(
        self, message: str, history: list[HistoryItem]
    ) -> str:
        if self._retriever is None:
            return ""
        query = self._build_retrieval_query(message, history)
        if not query.strip():
            return ""
        try:
            chunks = await self._retriever.retrieve(query)
        except Exception:
            return ""
        if not chunks:
            return ""
        parts = [f"[{chunk.title}] {chunk.text}" for chunk in chunks]
        return format_rag_context("\n\n".join(parts))

    @staticmethod
    def _build_retrieval_query(message: str, history: list[HistoryItem]) -> str:
        parts = [message]
        user_messages = [
            item.content for item in history if item.role == HistoryRole.USER
        ]
        parts.extend(user_messages[-2:])
        return " ".join(parts)
