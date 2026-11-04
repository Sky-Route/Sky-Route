"""API Layer: forma del JSON de respuesta (Pydantic v2)."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
