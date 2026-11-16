"""Dependencia transversal de validación de token JWT Bearer en la capa API (HU-001)."""
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_jwt_token
from app.domain.exceptions.domain_exceptions import AppError

bearer_scheme = HTTPBearer(auto_error=False, description="Token JWT emitido por POST /api/v1/auth/token")


def require_auth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Verifica que la petición incluya Authorization: Bearer <accessToken> válido y vigente."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AppError("La credencial no es válida o no está activa", status_code=401)
    try:
        return decode_jwt_token(credentials.credentials)
    except ValueError as exc:
        raise AppError("La credencial no es válida o no está activa", status_code=401) from exc
