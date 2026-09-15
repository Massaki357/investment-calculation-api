from fastapi import APIRouter

from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Liveness probe for Docker, orchestrators and the JARVIS client. "
    "Does not require authentication.",
)
def health() -> HealthResponse:
    return HealthResponse()
