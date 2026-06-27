from collections.abc import Sequence
from dataclasses import dataclass, field

from app.schemas.advice import AdviceProviderResult, WellnessLog
from app.schemas.chat import ChatProviderResult, HistoryItem


@dataclass
class FakeLLMProvider:
    """Recording, network-free provider for service and route tests. Author: 2692341798."""

    chat_result: ChatProviderResult = field(
        default_factory=lambda: ChatProviderResult(
            content="A short wellness reply.", model="deepseek-v4-flash"
        )
    )
    advice_result: AdviceProviderResult = field(
        default_factory=lambda: AdviceProviderResult(
            advice_text="A short wellness suggestion.", model="deepseek-v4-flash"
        )
    )
    error: Exception | None = None
    chat_calls: list[dict[str, object]] = field(default_factory=list)
    advice_calls: list[dict[str, object]] = field(default_factory=list)

    async def generate_chat(
        self, *, message: str, history: Sequence[HistoryItem]
    ) -> ChatProviderResult:
        """Record a chat call and return its configured result. Author: 2692341798."""
        self.chat_calls.append({"message": message, "history": list(history)})
        if self.error is not None:
            raise self.error
        return self.chat_result

    async def generate_advice(
        self, *, logs: Sequence[WellnessLog]
    ) -> AdviceProviderResult:
        """Record an advice call and return its configured result. Author: 2692341798."""
        self.advice_calls.append({"logs": list(logs)})
        if self.error is not None:
            raise self.error
        return self.advice_result
