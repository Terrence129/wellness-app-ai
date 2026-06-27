from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.schemas.advice import AdviceProviderResult, WellnessLog
from app.schemas.chat import ChatProviderResult, HistoryItem


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-independent asynchronous generation boundary. Author: 2692341798."""

    async def generate_chat(
        self, *, message: str, history: Sequence[HistoryItem]
    ) -> ChatProviderResult:
        """Generate one wellness-chat reply. Author: 2692341798."""
        ...

    async def generate_advice(
        self, *, logs: Sequence[WellnessLog]
    ) -> AdviceProviderResult:
        """Generate structured advice from validated wellness logs. Author: 2692341798."""
        ...

