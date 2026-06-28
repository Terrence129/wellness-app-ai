from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings
from app.providers.base import LLMProvider
from app.providers.ollama import OllamaProvider
from app.services.advice import AdviceService

DeepSeekProvider = OllamaProvider
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


def get_chat_service(
    provider: Annotated[LLMProvider, Depends(get_provider)],
) -> ChatService:
    """Construct the chat application service. Author: 2692341798."""
    return ChatService(provider, SafetyPolicy())


def get_advice_service(
    provider: Annotated[LLMProvider, Depends(get_provider)],
) -> AdviceService:
    """Construct the advice application service. Author: 2692341798."""
    return AdviceService(provider)
