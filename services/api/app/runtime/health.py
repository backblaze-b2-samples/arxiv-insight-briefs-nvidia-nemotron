"""Health endpoint — B2 connectivity + NVIDIA API key presence."""

from fastapi import APIRouter

from app.config import settings
from app.service.health import check_b2

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Snapshot of upstream reachability.

    `nvidia_configured` is just "is the key set?" — no live probe (this
    endpoint is hit every 60s by the UI banner).
    """
    b2_ok = check_b2()
    return {
        "status": "healthy" if b2_ok else "degraded",
        "b2_connected": b2_ok,
        "nvidia_configured": bool(settings.nvidia_api_key),
    }
