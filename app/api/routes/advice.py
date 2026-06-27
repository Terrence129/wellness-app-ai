from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_advice_service
from app.core.logging import get_request_id
from app.schemas.advice import AdviceRequest, AdviceResponse
from app.services.advice import AdviceService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/wellness-advice",
    response_model=AdviceResponse,
    response_model_by_alias=True,
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
