"""Router de Estado Operativo de Vuelos, Alertas al Pasajero, Check-in y Pases de Abordaje (HU-014 a HU-018)."""
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.auth import require_auth_token
from app.api.schemas.auth import StandardResponse
from app.api.schemas.operaciones import ActualizarEstatusVueloRequest, RealizarCheckinRequest
from app.services.services.operacion_service import OperacionService

router = APIRouter(
    prefix="/api/v1",
    tags=["Operaciones de Vuelo, Alertas y Check-in (HU-014 a HU-018)"],
    dependencies=[Depends(require_auth_token)],
)


@router.patch(
    "/vuelos/{idVuelo}/estatus",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar el estado operativo de un vuelo y publicar evento vuelo.estatus.cambiado (HU-014)",
)
def actualizar_estatus_vuelo(
    idVuelo: str,
    payload: ActualizarEstatusVueloRequest,
    token_payload: dict[str, Any] = Depends(require_auth_token),
) -> StandardResponse:
    data = OperacionService().actualizar_estatus_vuelo(
        id_vuelo=idVuelo,
        estado_nuevo=payload.estado,
        puerta=payload.puerta,
        hora_estimada_salida=payload.horaEstimadaSalida,
        fuente=payload.fuente,
        observacion=payload.observacion,
        alcance_token=token_payload.get("scope", []),
    )
    return StandardResponse(
        mensaje="Estado del vuelo actualizado",
        data=data,
        success=True,
    )


@router.get(
    "/vuelos/{idVuelo}/estatus",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar el estado operativo vigente, puerta y hora estimada de un vuelo (HU-016)",
)
def consultar_estatus_vuelo(idVuelo: str) -> StandardResponse:
    data = OperacionService().consultar_estatus_vuelo(idVuelo)
    return StandardResponse(
        mensaje="Consulta del estado del vuelo exitosa",
        data=data,
        success=True,
    )


@router.get(
    "/alertas",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar las alertas operativas enviadas a un pasajero por cambios de vuelo (HU-015 · RN-27)",
)
def consultar_alertas(idPasajero: str = Query(..., examples=["PAS-3102"])) -> StandardResponse:
    data = OperacionService().consultar_alertas_pasajero(idPasajero)
    return StandardResponse(
        mensaje="Consulta de alertas exitosa",
        data=data,
        success=True,
    )


@router.get(
    "/vuelos/{idVuelo}/ventana-checkin",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar si la ventana de check-in (24 a 2 horas antes) está abierta (HU-017 · RN-16)",
)
def consultar_ventana_checkin(idVuelo: str) -> StandardResponse:
    data = OperacionService().consultar_ventana_checkin(idVuelo)
    return StandardResponse(
        mensaje="Consulta de ventana de check-in exitosa",
        data=data,
        success=True,
    )


@router.post(
    "/checkin",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Realizar el check-in en línea dentro de la ventana reglamentaria (HU-017 · RN-16)",
)
def realizar_checkin(payload: RealizarCheckinRequest) -> StandardResponse:
    data = OperacionService().realizar_checkin(
        codigo_pnr=payload.codigoPnr,
        id_pasajero=payload.idPasajero,
        id_vuelo=payload.idVuelo,
    )
    return StandardResponse(
        mensaje="Check-in realizado",
        data=data,
        success=True,
    )


@router.get(
    "/pases-abordaje",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener tarjeta de embarque digital con código QR firmado (HU-018)",
)
def consultar_pase_abordaje(
    codigoPnr: str = Query(..., examples=["K7Q2MZ"]),
    idPasajero: str = Query(..., examples=["PAS-3102"]),
) -> StandardResponse:
    data = OperacionService().consultar_pase_abordaje(codigo_pnr=codigoPnr, id_pasajero=idPasajero)
    return StandardResponse(
        mensaje="Pase de abordaje generado",
        data=data,
        success=True,
    )
