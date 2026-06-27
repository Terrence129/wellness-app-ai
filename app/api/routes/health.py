from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Report process availability without exposing configuration.

    Author: 2692341798
    """
    return {"status": "ok", "service": "wellness-app-ai"}
