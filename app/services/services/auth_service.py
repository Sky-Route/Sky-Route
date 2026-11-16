"""Service Layer: Registro de credenciales de API y emisión de tokens JWT (MOD-05 · HU-001)."""
from typing import Any

from app.core.security import (
    TOKEN_EXPIRE_SECONDS,
    create_jwt_token,
    generate_plain_secret,
    hash_client_secret,
    verify_client_secret,
)
from app.domain.entities.auth import validar_alcances_registro, validar_credencial_y_alcance_rn25
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.repositories.auth_repository import AuthRepository


class AuthService:
    def __init__(self, repository: AuthRepository | None = None):
        self.repository = repository or AuthRepository()

    def registrar_credencial(
        self,
        nombre_aplicacion: str,
        responsable: str,
        alcance: list[str],
        client_id: str | None = None,
        client_secret_fijo: str | None = None,
        estado: str = "activa",
    ) -> dict[str, Any]:
        validar_alcances_registro(alcance)
        plain_secret = client_secret_fijo or generate_plain_secret()
        secret_hash = hash_client_secret(plain_secret)
        credencial = self.repository.guardar_credencial(
            nombre_aplicacion=nombre_aplicacion,
            responsable=responsable,
            alcance=alcance,
            secret_hash=secret_hash,
            client_id=client_id,
            estado=estado,
        )
        return {
            "idCredencial": credencial.id_credencial,
            "clientId": credencial.client_id,
            "clientSecret": plain_secret,
            "alcance": credencial.alcance,
            "estado": credencial.estado,
            "fechaExpiracion": credencial.fecha_expiracion,
        }

    def emitir_token(self, client_id: str, client_secret: str, alcance: list[str]) -> dict[str, Any]:
        credencial = self.repository.obtener_por_client_id(client_id)
        secret_ok = verify_client_secret(client_secret, credencial.secret_hash) if credencial else False
        alcance_validado = validar_credencial_y_alcance_rn25(
            credencial=credencial,
            secret_valido=secret_ok,
            alcance_solicitado=alcance,
        )
        token, jti, exp_ts = create_jwt_token(
            client_id=credencial.client_id,
            alcance=alcance_validado,
            expires_in=TOKEN_EXPIRE_SECONDS,
        )
        self.repository.guardar_token_emitido(
            jti=jti,
            client_id=credencial.client_id,
            alcance=alcance_validado,
            expira_en=TOKEN_EXPIRE_SECONDS,
            exp_ts=exp_ts,
        )
        return {
            "accessToken": token,
            "tipo": "Bearer",
            "expiraEn": TOKEN_EXPIRE_SECONDS,
            "alcance": alcance_validado,
        }

    def revocar_credencial(self, client_id: str) -> dict[str, Any]:
        cred = self.repository.cambiar_estado_credencial(client_id, "revocada")
        if not cred:
            raise AppError("La credencial indicada no existe", status_code=404)
        return {
            "idCredencial": cred.id_credencial,
            "clientId": cred.client_id,
            "estado": cred.estado,
        }
