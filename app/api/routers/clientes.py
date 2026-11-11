"""Router de Privacidad (API-22 · MOD-07 · HU-005) y Registro de Pasajeros (API-04 · MOD-02 · HU-006)."""
from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import require_auth_token
from app.api.schemas.auth import StandardResponse
from app.api.schemas.clientes import RegistrarConsentimientoRequest, RegistrarPasajeroRequest
from app.domain.exceptions.domain_exceptions import AppError
from app.services.services.cliente_service import ClienteService

router = APIRouter(
    prefix="/api/v1",
    tags=["Privacidad y Pasajeros (HU-005, HU-006)"],
    dependencies=[Depends(require_auth_token)],
)


@router.post(
    "/privacidad/consentimientos",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar consentimiento de tratamiento de datos personales por finalidad (HU-005 · RN-35)",
)
def registrar_consentimiento(payload: RegistrarConsentimientoRequest) -> StandardResponse:
    titular_dict = payload.titular.model_dump() if payload.titular else None
    finalidades_list = [f.model_dump() for f in payload.finalidades]
    data = ClienteService().registrar_consentimiento(
        titular=titular_dict,
        finalidades=finalidades_list,
        canal=payload.canal,
    )
    return StandardResponse(
        mensaje="Consentimiento registrado",
        data=data,
        success=True,
    )


@router.get(
    "/privacidad/consentimientos/{idConsentimiento}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar consentimiento registrado (API-22.2 · HU-005, HU-006)",
)
def consultar_consentimiento(idConsentimiento: str) -> StandardResponse:
    data = ClienteService().repository.obtener_consentimiento(idConsentimiento)
    if not data:
        raise AppError("El consentimiento indicado no existe", status_code=404)
    return StandardResponse(
        mensaje="Consulta de consentimiento exitosa",
        data=data,
        success=True,
    )


@router.post(
    "/pasajeros",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar datos e identificación de un pasajero (HU-006 · RN-06, RN-35)",
)
def registrar_pasajero(payload: RegistrarPasajeroRequest) -> StandardResponse:
    data = ClienteService().registrar_pasajero(
        nombres=payload.nombres,
        apellidos=payload.apellidos,
        tipo_documento=payload.tipoDocumento,
        numero_documento=payload.numeroDocumento,
        fecha_nacimiento=payload.fechaNacimiento,
        correo=payload.correo,
        telefono=payload.telefono,
        id_consentimiento=payload.idConsentimiento,
    )
    return StandardResponse(
        mensaje="Pasajero registrado",
        data=data,
        success=True,
    )
