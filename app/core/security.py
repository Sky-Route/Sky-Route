"""Parámetros de seguridad, hash de secretos y emisión/validación de tokens JWT (HU-001)."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
TOKEN_EXPIRE_SECONDS = 3600


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def hash_client_secret(secret: str) -> str:
    """Genera hash SHA-256 con sal derivada para no almacenar el secreto en texto plano (FUN-099)."""
    return hmac.new(SECRET_KEY.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_client_secret(plain_secret: str, secret_hash: str) -> bool:
    """Compara en tiempo constante el secreto recibido con el hash almacenado."""
    expected = hash_client_secret(plain_secret)
    return hmac.compare_digest(expected, secret_hash)


def generate_plain_secret() -> str:
    """Genera un secreto aleatorio seguro que se entrega una única vez."""
    return f"sr_live_{secrets.token_urlsafe(18)}"


def create_jwt_token(client_id: str, alcance: list[str], expires_in: int = TOKEN_EXPIRE_SECONDS) -> tuple[str, str, int]:
    """Emite un token JWT firmado (HS256) con identificador jti, alcance y vencimiento."""
    now = int(time.time())
    exp = now + expires_in
    jti = f"TOK-{secrets.token_hex(6).upper()}"
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": client_id,
        "scope": alcance,
        "iat": now,
        "exp": exp,
        "jti": jti,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    token = f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"
    return token, jti, exp


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Valida firma y expiración de un token JWT. Lanza ValueError si es inválido o vencido."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Formato de token inválido")
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Firma de token inválida")
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Token expirado")
        return payload
    except Exception as exc:
        raise ValueError(str(exc)) from exc
