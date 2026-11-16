"""Esquemas Pydantic para Estatus de Vuelo, Alertas, Check-in y Pases de Abordaje (HU-014 a HU-018)."""
from pydantic import BaseModel, Field


class ActualizarEstatusVueloRequest(BaseModel):
    estado: str = Field(..., examples=["Retrasado"])
    puerta: str | None = Field(default="B12", examples=["B12"])
    horaEstimadaSalida: str | None = Field(default=None, examples=["2026-11-20T09:30:00-05:00"])
    fuente: str = Field(default="aerolinea", examples=["aerolinea"])
    observacion: str | None = Field(default=None, examples=["Llegada tardía de la aeronave"])


class RealizarCheckinRequest(BaseModel):
    codigoPnr: str = Field(..., examples=["K7Q2MZ"])
    idPasajero: str = Field(..., examples=["PAS-3102"])
    idVuelo: str = Field(..., examples=["VU-1023"])
