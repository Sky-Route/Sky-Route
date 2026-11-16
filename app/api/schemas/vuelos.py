"""Esquemas Pydantic para Itinerarios, Mapa de Asientos y Bloqueos (MOD-01 · HU-002, HU-003, HU-004, HU-012)."""
from pydantic import BaseModel, Field


class BloquearAsientoRequest(BaseModel):
    idVuelo: str = Field(..., examples=["VU-1023"])
    numeroAsiento: str = Field(..., examples=["14C"])
    idSesionCompra: str = Field(..., examples=["SES-88213"])


class ConfirmarBloqueoRequest(BaseModel):
    codigoPnr: str = Field(..., examples=["K7Q2MZ"])
