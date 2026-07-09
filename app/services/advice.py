# Author: Huang Qijun
# Email: 2692341798@qq.com

from app.core.exceptions import AppError
from app.providers.base import LLMProvider
from app.schemas.advice import AdviceProviderResult, AdviceRequest, AdviceResponse

NO_DATA_ADVICE = (
    "There is not enough wellness data yet. Record your sleep, mood, water intake, "
    "and exercise for a few days."
)


class AdviceService:
    """Generate provider-independent wellness advice. Author: 2692341798."""

    def __init__(self, provider: LLMProvider) -> None:
        """Store the configured provider dependency. Author: 2692341798."""
        self._provider = provider

    async def generate(self, request: AdviceRequest, request_id: str) -> AdviceResponse:
        """Generate advice for one validated request. Author: 2692341798."""
        if not request.logs:
            return AdviceResponse(advice_text=NO_DATA_ADVICE, request_id=request_id)

        result = await self._provider.generate_advice(logs=request.logs)
        if not isinstance(result, AdviceProviderResult):
            raise AppError.invalid_response()

        raw_advice_text = getattr(result, "advice_text", None)
        if not isinstance(raw_advice_text, str):
            raise AppError.invalid_response()

        advice_text = raw_advice_text.strip()
        if not advice_text:
            raise AppError.invalid_response()
        return AdviceResponse(advice_text=advice_text, request_id=request_id)
