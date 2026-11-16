"""Repository Layer: único punto que toca la base de datos."""
from app.core.database import database_is_up


class HealthRepository:
    def database_available(self) -> bool:
        try:
            return database_is_up()
        except Exception:
            return False
