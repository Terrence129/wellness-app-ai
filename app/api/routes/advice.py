from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_advice_service
from app.core.logging import get_request_id
from app.schemas.advice import AdviceRequest, AdviceResponse
from app.services.advice import AdviceService

router = APIRouter(prefix="/ai", tags=["AI Advice"])


_ADVICE_DESC = (
    "Generate personalised wellness advice from one or more daily "
    "wellness logs.\n\n"
    "**Deterministic no-data path**: When `logs` is empty, the service "
    "returns a stable prompt encouraging the user to record data for "
    "a few days — without calling DeepSeek at all. This path works "
    "even when no provider key is configured.\n\n"
    "**Provider path**: When wellness logs are supplied, the request "
    "is sent to DeepSeek with strict JSON output constraints. The "
    "response is validated against the `AdvicePayload` schema and "
    "rejected if empty, truncated, or schema-incompatible.\n\n"
    "**Privacy**: The internal `userId` and user notes are never sent "
    "to DeepSeek. Logs exclude raw messages, prompts, and generated text."
)


@router.post(
    "/wellness-advice",
    response_model=AdviceResponse,
    response_model_by_alias=True,
    summary="Wellness Advice",
    description=_ADVICE_DESC,
)
async def wellness_advice(
    request: AdviceRequest,
    service: Annotated[AdviceService, Depends(get_advice_service)],
) -> AdviceResponse:
    """Generate grounded advice from bounded wellness logs. Author: 2692341798."""
    request_id = get_request_id()
    if request_id is None:
        raise RuntimeError("request ID context is unavailable")
    return await service.generate(request, request_id)
