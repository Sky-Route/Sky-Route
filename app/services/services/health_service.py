"""Service Layer: coordina el caso de uso y usa el repositorio."""
from app.core.config import settings
from app.domain.entities.health import ServiceHealth
from app.repositories.repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, repository: HealthRepository | None = None):
        self.repository = repository or HealthRepository()

    def check(self) -> ServiceHealth:
        status = "ok" if self.repository.database_available() else "degraded"
        return ServiceHealth(status=status, version=settings.APP_VERSION, environment=settings.APP_ENV)
