"""Router de Itinerarios, Mapa de Asientos y Bloqueos (API-01 y API-02 · MOD-01 · HU-002, HU-003, HU-004, HU-012)."""
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.auth import require_auth_token
from app.api.schemas.auth import StandardResponse
from app.api.schemas.vuelos import BloquearAsientoRequest, ConfirmarBloqueoRequest
from app.services.services.vuelo_service import VueloService

router = APIRouter(
    prefix="/api/v1",
    tags=["Itinerarios y Asientos (HU-002, HU-003, HU-004, HU-012)"],
    dependencies=[Depends(require_auth_token)],
)


@router.get(
    "/itinerarios",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar vuelos disponibles con tarifa vigente y cupos (HU-002 · RN-04, RN-05)",
)
def consultar_itinerarios(
    origen: str = Query(..., examples=["BOG"]),
    destino: str = Query(..., examples=["MDE"]),
    fechaDesde: str = Query(..., examples=["2026-11-20"]),
    fechaHasta: str = Query(..., examples=["2026-11-20"]),
    cupos: int = Query(1, examples=[2]),
) -> StandardResponse:
    mensaje, itinerarios = VueloService().buscar_itinerarios(
        origen=origen,
        destino=destino,
        fecha_desde=fechaDesde,
        fecha_hasta=fechaHasta,
        cupos=cupos,
    )
    return StandardResponse(
        mensaje=mensaje,
        data={"itinerarios": itinerarios},
        success=True,
    )


@router.get(
    "/vuelos/{idVuelo}/asientos",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar mapa de asientos por cabina y estado (HU-003 · RN-05)",
)
def consultar_mapa_asientos(idVuelo: str) -> StandardResponse:
    data = VueloService().consultar_mapa_asientos(idVuelo)
    return StandardResponse(
        mensaje="Consulta del mapa de asientos exitosa",
        data=data,
        success=True,
    )


@router.post(
    "/asientos/bloqueos",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apartar temporalmente un asiento durante 15 minutos (HU-004 · RN-01)",
)
def bloquear_asiento(payload: BloquearAsientoRequest) -> StandardResponse:
    data = VueloService().bloquear_asiento(
        id_vuelo=payload.idVuelo,
        numero_asiento=payload.numeroAsiento,
        id_sesion_compra=payload.idSesionCompra,
    )
    return StandardResponse(
        mensaje="Asiento bloqueado temporalmente",
        data=data,
        success=True,
    )


@router.post(
    "/asientos/bloqueos/{idBloqueo}/confirmacion",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirmar bloqueo temporal de asiento al emitir PNR (API-02.3 · HU-007)",
)
def confirmar_bloqueo(idBloqueo: str, payload: ConfirmarBloqueoRequest) -> StandardResponse:
    data = VueloService().repository.confirmar_bloqueo(idBloqueo, payload.codigoPnr)
    return StandardResponse(
        mensaje="Bloqueo de asiento confirmado",
        data=data,
        success=True,
    )


@router.get(
    "/asientos/bloqueos",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar bloqueos de asientos vencidos (API-02.4 · HU-012)",
)
def listar_bloqueos(vencidos: bool = Query(True)) -> StandardResponse:
    lista = VueloService().repository.listar_bloqueos_vencidos() if vencidos else []
    return StandardResponse(
        mensaje="Consulta de bloqueos exitosa",
        data={"bloqueos": lista},
        success=True,
    )


@router.delete(
    "/asientos/bloqueos/{idBloqueo}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Liberar un bloqueo de asiento por vencimiento o cancelación (HU-012 · RN-01)",
)
def liberar_bloqueo(
    idBloqueo: str,
    motivo: str = Query("vencimiento", examples=["vencimiento"]),
) -> StandardResponse:
    data = VueloService().liberar_bloqueo(id_bloqueo=idBloqueo, motivo=motivo)
    return StandardResponse(
        mensaje="Bloqueo liberado",
        data=data,
        success=True,
    )
