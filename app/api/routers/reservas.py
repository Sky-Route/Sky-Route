"""Router de Reservas, Equipaje, Cobros, Vencimientos y Cancelaciones/Reembolsos (HU-007 a HU-013)."""
from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse

from app.api.dependencies.auth import require_auth_token
from app.api.schemas.auth import StandardResponse
from app.api.schemas.reservas import (
    AgregarEquipajeRequest,
    AprobarReembolsoRequest,
    CancelarReservaRequest,
    CrearReembolsoDirectoRequest,
    CrearReservaRequest,
    ProcesarCobroRequest,
)
from app.services.services.reserva_service import ReservaService

router = APIRouter(
    prefix="/api/v1",
    tags=["Reservas, Equipajes, Cobros y Cancelaciones (HU-007 a HU-013)"],
    dependencies=[Depends(require_auth_token)],
)


@router.post(
    "/reservas",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear reserva con código PNR único en estado Pendiente de pago (HU-007 · RN-01, RN-06)",
)
def crear_reserva(payload: CrearReservaRequest) -> StandardResponse:
    data = ReservaService().crear_reserva(
        id_vuelo=payload.idVuelo,
        pasajeros_input=[p.model_dump() for p in payload.pasajeros],
    )
    return StandardResponse(mensaje="Reserva creada", data=data, success=True)


@router.get(
    "/reservas/{codigoPnr}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar el estado, vuelos, pasajeros y saldo de una reserva (HU-011)",
)
def consultar_reserva(
    codigoPnr: str,
    apellido: str | None = Query(default=None, examples=["Gomez"]),
) -> StandardResponse:
    data = ReservaService().consultar_reserva(codigo_pnr=codigoPnr, apellido=apellido)
    return StandardResponse(mensaje="Consulta de reserva exitosa", data=data, success=True)


@router.get(
    "/reservas/{codigoPnr}/servicios-suplementarios",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar catálogo de opciones de equipaje adicional para una reserva (HU-008)",
)
def listar_servicios_suplementarios(codigoPnr: str) -> StandardResponse:
    data = ReservaService().listar_opciones_equipaje(codigoPnr)
    return StandardResponse(
        mensaje="Catálogo de servicios suplementarios consultado",
        data=data,
        success=True,
    )


@router.post(
    "/reservas/{codigoPnr}/equipajes",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar equipaje adicional a una reserva vigente y recalcular saldo (HU-008 · RN-10)",
)
def agregar_equipaje(codigoPnr: str, payload: AgregarEquipajeRequest) -> StandardResponse:
    data = ReservaService().agregar_equipaje(
        codigo_pnr=codigoPnr,
        id_pasajero=payload.idPasajero,
        tipo=payload.tipo,
        peso_kg=payload.pesoKg,
        piezas=payload.piezas,
    )
    return StandardResponse(mensaje="Equipaje adicional registrado", data=data, success=True)


@router.post(
    "/cobros",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pagar la reserva con tarjeta e idempotencia mediante simulador de Wompi (HU-009 · RN-10, RN-12)",
)
def procesar_cobro(
    payload: ProcesarCobroRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    http_code, mensaje, ok, data = ReservaService().procesar_cobro(
        codigo_pnr=payload.codigoPnr,
        monto=payload.monto,
        moneda=payload.moneda,
        token_medio_pago=payload.tokenMedioPago,
        concepto=payload.concepto,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(
        status_code=http_code,
        content={"mensaje": mensaje, "data": data, "success": ok},
    )


@router.post(
    "/reservas/vencimientos/ejecutar",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Disparar tarea programada de liberación de asientos y reservas vencidas (HU-012 · RN-01, RN-10)",
)
def ejecutar_vencimientos() -> StandardResponse:
    data = ReservaService().ejecutar_liberacion_automatica()
    return StandardResponse(
        mensaje="Proceso de liberación de vencimientos ejecutado",
        data=data,
        success=True,
    )


@router.post(
    "/reservas/{codigoPnr}/cancelaciones",
    response_model=StandardResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cancelar una reserva, calcular penalidad RN-07 y ordenar reembolso con doble control RN-15 (HU-013)",
)
def cancelar_reserva(codigoPnr: str, payload: CancelarReservaRequest) -> JSONResponse:
    http_code, mensaje, data = ReservaService().cancelar_reserva(
        codigo_pnr=codigoPnr,
        apellido=payload.apellido,
        motivo=payload.motivo,
    )
    return JSONResponse(
        status_code=http_code,
        content={"mensaje": mensaje, "data": data, "success": True},
    )


@router.post(
    "/reembolsos",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear orden de reembolso sujeta a aprobación de segundo responsable (API-06.2 · HU-013 · RN-15)",
)
def crear_reembolso(payload: CrearReembolsoDirectoRequest) -> StandardResponse:
    orden = ReservaService().reserva_repo.crear_orden_reembolso(
        id_transaccion_original=payload.idTransaccionOriginal,
        codigo_pnr=payload.codigoPnr,
        penalidad_valor=0,
        monto_reembolso=payload.montoReembolso,
        motivo=payload.motivo,
    )
    return StandardResponse(
        mensaje="Orden de reembolso creada en estado Pendiente de aprobación",
        data=orden,
        success=True,
    )


@router.post(
    "/reembolsos/{idReembolso}/aprobaciones",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprobar o rechazar reembolso por segundo responsable y ejecutar reverso en Wompi (API-06.3 · HU-013 · RN-15)",
)
def aprobar_reembolso(idReembolso: str, payload: AprobarReembolsoRequest) -> StandardResponse:
    data = ReservaService().aprobar_reembolso(
        id_reembolso=idReembolso,
        aprobador=payload.aprobador,
        decision=payload.decision,
        observacion=payload.observacion,
    )
    return StandardResponse(
        mensaje="Reembolso procesado con doble control",
        data=data,
        success=True,
    )
