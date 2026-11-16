"""Domain Layer: entidad sin dependencias de HTTP, JSON ni SQL."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceHealth:
    status: str
    version: str
    environment: str
