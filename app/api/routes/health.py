# Author: Huang Qijun
# Email: 2692341798@qq.com

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health Check",
    description=(
        "Report process availability. This endpoint does not call DeepSeek and "
        "works even when no provider key is configured. The response must not "
        "expose configuration values, model credentials, dependency versions, "
        "or environment variables."
    ),
)
async def health() -> dict[str, str]:
    """Report process availability without exposing configuration.

    Author: 2692341798
    """
    return {"status": "ok", "service": "wellness-app-ai"}
