"""Esquemas Pydantic para Reservas, Equipaje, Cobros y Cancelaciones/Reembolsos (HU-007 a HU-013)."""
from pydantic import BaseModel, Field


class PasajeroReservaItemSchema(BaseModel):
    idPasajero: str = Field(..., examples=["PAS-3102"])
    idBloqueo: str = Field(..., examples=["BLQ-55821"])


class CrearReservaRequest(BaseModel):
    idVuelo: str = Field(..., examples=["VU-1023"])
    pasajeros: list[PasajeroReservaItemSchema]


class AgregarEquipajeRequest(BaseModel):
    idPasajero: str = Field(..., examples=["PAS-3102"])
    tipo: str = Field(..., examples=["bodega"])
    pesoKg: int = Field(..., examples=[23])
    piezas: int = Field(default=1, examples=[1])


class ProcesarCobroRequest(BaseModel):
    codigoPnr: str = Field(..., examples=["K7Q2MZ"])
    monto: int = Field(..., examples=[384000])
    moneda: str = Field(default="COP", examples=["COP"])
    tokenMedioPago: str = Field(..., examples=["tok_4f9a21c7"])
    concepto: str = Field(default="reserva", examples=["reserva"])


class CancelarReservaRequest(BaseModel):
    apellido: str = Field(..., examples=["Gomez"])
    motivo: str = Field(..., examples=["Cambio de planes"])


class CrearReembolsoDirectoRequest(BaseModel):
    idTransaccionOriginal: str = Field(..., examples=["TRX-90213"])
    codigoPnr: str = Field(..., examples=["K7Q2MZ"])
    montoReembolso: int = Field(..., examples=[324000])
    motivo: str = Field(..., examples=["Cancelación voluntaria"])


class AprobarReembolsoRequest(BaseModel):
    aprobador: str = Field(..., examples=["supervisor.tesoreria"])
    decision: str = Field(..., examples=["aprobar"])
    observacion: str | None = Field(default="Doble control verificado (RN-15)")
