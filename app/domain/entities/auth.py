"""Domain Layer: Regla de negocio RN-25 y entidad CredencialDeAPI (HU-001)."""
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.exceptions.domain_exceptions import AppError

ALCANCES_CATALOGO = {
    "itinerarios:leer",
    "asientos:leer",
    "asientos:escribir",
    "privacidad:escribir",
    "pasajeros:escribir",
    "reservas:leer",
    "reservas:escribir",
    "pagos:escribir",
    "facturas:leer",
    "vuelos:escribir",
    "vuelos:leer",
    "alertas:leer",
    "checkin:escribir",
    "pases:leer",
}


@dataclass
class CredencialDeAPI:
    id_credencial: str
    client_id: str
    nombre_aplicacion: str
    responsable: str
    secret_hash: str
    alcance: list[str]
    estado: str
    fecha_expiracion: str


def validar_alcances_registro(alcance: list[str]) -> None:
    """Valida que la aplicación solicite al menos un alcance válido al registrarse (FUN-099)."""
    if not alcance:
        raise AppError("Debe indicar al menos un alcance autorizado para la aplicación", status_code=400)


def validar_credencial_y_alcance_rn25(
    credencial: CredencialDeAPI | None,
    secret_valido: bool,
    alcance_solicitado: list[str],
    ahora: datetime | None = None,
) -> list[str]:
    """RN-25: Verifica que la credencial exista, esté activa, no vencida ni revocada y que el alcance esté autorizado."""
    if credencial is None or not secret_valido:
        raise AppError("La credencial no es válida o no está activa", status_code=401)

    if credencial.estado.lower() != "activa":
        raise AppError("La credencial no es válida o no está activa", status_code=401)

    ahora_dt = ahora or datetime.now(timezone.utc)
    try:
        exp_dt = datetime.fromisoformat(credencial.fecha_expiracion)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if ahora_dt >= exp_dt:
            raise AppError("La credencial no es válida o no está activa", status_code=401)
    except AppError:
        raise
    except ValueError:
        pass

    if not alcance_solicitado:
        raise AppError("Debe especificar al menos un alcance para el token", status_code=400)

    autorizados = set(credencial.alcance)
    if "*" not in autorizados:
        for scope in alcance_solicitado:
            if scope not in autorizados:
                raise AppError(
                    "El alcance solicitado no está autorizado para esta aplicación",
                    status_code=403,
                )

    return list(alcance_solicitado)
