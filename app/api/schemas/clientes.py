"""Esquemas Pydantic para Consentimientos de Privacidad (HU-005) y Pasajeros (HU-006)."""
from pydantic import BaseModel, Field


class TitularSchema(BaseModel):
    tipoDocumento: str | None = Field(default=None, examples=["CC"])
    numeroDocumento: str | None = Field(default=None, examples=["1098765432"])


class FinalidadDecisionSchema(BaseModel):
    finalidad: str = Field(..., examples=["operativa"])
    decision: str = Field(..., examples=["acepta"])


class RegistrarConsentimientoRequest(BaseModel):
    titular: TitularSchema | None = None
    finalidades: list[FinalidadDecisionSchema] = Field(
        ...,
        examples=[
            [
                {"finalidad": "operativa", "decision": "acepta"},
                {"finalidad": "comercial", "decision": "no acepta"},
            ]
        ],
    )
    canal: str = Field(..., examples=["web"])


class RegistrarPasajeroRequest(BaseModel):
    nombres: str = Field(..., examples=["Laura"])
    apellidos: str = Field(..., examples=["Gómez Ruiz"])
    tipoDocumento: str = Field(..., examples=["CC"])
    numeroDocumento: str = Field(..., examples=["1098765432"])
    fechaNacimiento: str = Field(..., examples=["1995-04-12"])
    correo: str = Field(..., examples=["laura.gomez@correo.com"])
    telefono: str = Field(..., examples=["+573001234567"])
    idConsentimiento: str = Field(..., examples=["CON-7781"])
