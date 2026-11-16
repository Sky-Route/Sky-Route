"""API Layer: expone el endpoint y delega en la capa de servicio."""
from fastapi import APIRouter

from app.api.schemas.health import HealthResponse
from app.services.services.health_service import HealthService

router = APIRouter(tags=["Sistema"])


@router.get("/health", response_model=HealthResponse, summary="Verificar que el servicio está activo")
def health() -> HealthResponse:
    result = HealthService().check()
    return HealthResponse(status=result.status, version=result.version, environment=result.environment)
