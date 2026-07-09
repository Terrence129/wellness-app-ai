# Author: Huang Qijun
# Email: 2692341798@qq.com

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings
from app.providers.base import LLMProvider
from app.providers.deepseek import DeepSeekProvider
from app.rag.retriever import Retriever
from app.services.advice import AdviceService
from app.services.chat import ChatService
from app.services.safety import SafetyPolicy


def get_settings(request: Request) -> Settings:
    """Return the settings owned by the current application. Author: 2692341798."""
    return cast(Settings, request.app.state.settings)


def get_provider(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMProvider:
    """Return one lazily constructed provider per application. Author: 2692341798."""
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        provider = DeepSeekProvider(settings)
        request.app.state.llm_provider = provider
    return cast(LLMProvider, provider)


def get_retriever(request: Request) -> Retriever | None:
    """Return the application-scoped RAG retriever. Author: 2692341798."""
    return cast(Retriever | None, getattr(request.app.state, "rag_retriever", None))


def get_chat_service(
    provider: Annotated[LLMProvider, Depends(get_provider)],
    retriever: Annotated[Retriever | None, Depends(get_retriever)],
) -> ChatService:
    """Construct the chat application service. Author: 2692341798."""
    return ChatService(provider, SafetyPolicy(), retriever)


def get_advice_service(
    provider: Annotated[LLMProvider, Depends(get_provider)],
) -> AdviceService:
    """Construct the advice application service. Author: 2692341798."""
    return AdviceService(provider)
