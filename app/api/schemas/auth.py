"""Esquemas Pydantic de entrada y salida para Autenticación (HU-001)."""
from typing import Any

from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    mensaje: str
    data: Any = None
    success: bool = True


class RegistrarCredencialRequest(BaseModel):
    nombreAplicacion: str = Field(..., examples=["frontend-web"], description="Nombre o identificador de la aplicación")
    responsable: str = Field(..., examples=["Integrador Técnico Web"], description="Responsable de la aplicación")
    alcance: list[str] = Field(
        ...,
        examples=[["itinerarios:leer", "reservas:escribir"]],
        description="Lista de alcances autorizados para la aplicación",
    )
    clientId: str | None = Field(default=None, examples=["frontend-web"])


class EmitirTokenRequest(BaseModel):
    clientId: str = Field(..., examples=["frontend-web"])
    clientSecret: str = Field(..., examples=["skyroute-secret-2026"])
    alcance: list[str] = Field(..., examples=[["itinerarios:leer", "reservas:escribir"]])
