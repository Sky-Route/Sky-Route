"""Router de Facturación Electrónica (API-07 · MOD-03 · HU-010)."""
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.auth import require_auth_token
from app.api.schemas.auth import StandardResponse
from app.services.services.factura_service import FacturaService

router = APIRouter(
    prefix="/api/v1",
    tags=["Facturación Electrónica (HU-010)"],
    dependencies=[Depends(require_auth_token)],
)


@router.post(
    "/facturas/reintentos",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Reintentar validación ante Alegra de las facturas en estado pendiente de validación (HU-010)",
)
def reintentar_facturas_pendientes() -> StandardResponse:
    data = FacturaService().reintentar_facturas_pendientes()
    return StandardResponse(
        mensaje="Reintento de facturas procesado",
        data=data,
        success=True,
    )


@router.get(
    "/facturas/{codigoPnr}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar y obtener enlaces PDF y XML de la factura electrónica de una reserva (HU-010 · RN-12)",
)
def consultar_factura(
    codigoPnr: str,
    apellido: str | None = Query(default=None, examples=["Gomez"]),
) -> StandardResponse:
    data = FacturaService().consultar_factura(codigo_pnr=codigoPnr, apellido=apellido)
    return StandardResponse(
        mensaje="Consulta de factura exitosa",
        data=data,
        success=True,
    )
