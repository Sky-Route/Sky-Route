"""Router de Autenticación y Credenciales de API (API-14 · MOD-05 · HU-001)."""
from fastapi import APIRouter, status

from app.api.schemas.auth import EmitirTokenRequest, RegistrarCredencialRequest, StandardResponse
from app.services.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación (HU-001)"])


def _error(descripcion: str, mensaje: str) -> dict:
    """Documenta en Swagger una respuesta de error con el formato estándar."""
    return {
        "model": StandardResponse,
        "description": descripcion,
        "content": {"application/json": {"example": {"mensaje": mensaje, "data": None, "success": False}}},
    }


@router.post(
    "/credenciales",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar aplicación consumidora y emitir su credencial única (FUN-099)",
    responses={400: _error("Alcance vacío", "Debe indicar al menos un alcance autorizado para la aplicación")},
)
def registrar_credencial(payload: RegistrarCredencialRequest) -> StandardResponse:
    data = AuthService().registrar_credencial(
        nombre_aplicacion=payload.nombreAplicacion,
        responsable=payload.responsable,
        alcance=payload.alcance,
        client_id=payload.clientId,
    )
    return StandardResponse(
        mensaje="Credencial registrada correctamente",
        data=data,
        success=True,
    )


@router.post(
    "/token",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Emitir token JWT de acceso para una aplicación autorizada (HU-001 · RN-25)",
    responses={
        400: _error("Alcance vacío", "Debe especificar al menos un alcance para el token"),
        401: _error("Credencial inválida, vencida o revocada", "La credencial no es válida o no está activa"),
        403: _error("Alcance no autorizado", "El alcance solicitado no está autorizado para esta aplicación"),
    },
)
def emitir_token(payload: EmitirTokenRequest) -> StandardResponse:
    data = AuthService().emitir_token(
        client_id=payload.clientId,
        client_secret=payload.clientSecret,
        alcance=payload.alcance,
    )
    return StandardResponse(
        mensaje="Token emitido correctamente",
        data=data,
        success=True,
    )


@router.patch(
    "/credenciales/{clientId}/revocar",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Revocar la credencial de una aplicación (FUN-100 / soporte de prueba RN-25)",
    responses={404: _error("Credencial inexistente", "La credencial indicada no existe")},
)
def revocar_credencial(clientId: str) -> StandardResponse:
    data = AuthService().revocar_credencial(clientId)
    return StandardResponse(
        mensaje="Credencial revocada correctamente",
        data=data,
        success=True,
    )
