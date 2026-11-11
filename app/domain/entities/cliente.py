"""Domain Layer: Reglas RN-35 (Privacidad · HU-005) y RN-06 (Pasajeros · HU-006)."""
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.domain.exceptions.domain_exceptions import AppError

TZ_COLOMBIA = timezone(timedelta(hours=-5))
FINALIDADES_AUTORIZADAS_RN35 = {"operativa", "comercial", "analitica", "analítica"}


def validar_consentimiento_rn35(
    titular: dict[str, Any] | None,
    finalidades: list[dict[str, str]],
    canal: str,
) -> bool:
    """RN-35 (HU-005): Valida documento del titular, catálogo de finalidades y determina si continúa la compra."""
    if not titular or not str(titular.get("tipoDocumento") or "").strip() or not str(titular.get("numeroDocumento") or "").strip():
        raise AppError("El documento del titular es obligatorio", status_code=400)

    if not finalidades:
        raise AppError("Debe indicar al menos una finalidad de tratamiento", status_code=400)

    if not (canal or "").strip():
        raise AppError("El canal de captura es obligatorio", status_code=400)

    operativa_aceptada = False
    for item in finalidades:
        fin = (item.get("finalidad") or "").strip().lower()
        dec = (item.get("decision") or "").strip().lower()
        if fin not in FINALIDADES_AUTORIZADAS_RN35:
            raise AppError(f"La finalidad '{item.get('finalidad')}' no está autorizada", status_code=422)
        if dec not in {"acepta", "no acepta"}:
            raise AppError("La decisión debe ser 'acepta' o 'no acepta'", status_code=400)
        if fin == "operativa" and dec == "acepta":
            operativa_aceptada = True

    return operativa_aceptada


def validar_y_clasificar_pasajero_rn06(
    nombres: str,
    apellidos: str,
    tipo_documento: str,
    numero_documento: str,
    fecha_nacimiento: str,
    correo: str,
    telefono: str,
    consentimiento_operativo_vigente: bool,
    fecha_referencia: date | None = None,
) -> str:
    """RN-06 y RN-35 (HU-006): Valida consentimiento operativo, documento, contacto y calcula tipoPasajero."""
    if not consentimiento_operativo_vigente:
        raise AppError(
            "El titular no ha autorizado el tratamiento de datos para la compra",
            status_code=422,
        )

    if not (nombres or "").strip() or not (apellidos or "").strip():
        raise AppError("Nombres y apellidos del pasajero son obligatorios", status_code=400)

    tdoc = (tipo_documento or "").strip().upper()
    ndoc = (numero_documento or "").strip()
    if not tdoc or not ndoc:
        raise AppError("El tipo y número de documento son obligatorios", status_code=400)

    if tdoc in {"CC", "TI", "RC"} and not ndoc.isdigit():
        raise AppError("El número de documento debe ser numérico para el tipo indicado", status_code=400)
    if tdoc in {"PA", "PASAPORTE", "CE"} and not ndoc.isalnum():
        raise AppError("El número de pasaporte o documento debe ser alfanumérico", status_code=400)

    if "@" not in (correo or "") or not (telefono or "").strip():
        raise AppError("Los datos de contacto (correo y teléfono) no son válidos", status_code=400)

    hoy = fecha_referencia or date(2026, 11, 10)
    try:
        fnac = date.fromisoformat(fecha_nacimiento)
    except Exception as exc:
        raise AppError("La fecha de nacimiento debe tener formato YYYY-MM-DD", status_code=400) from exc

    if fnac > hoy:
        raise AppError("La fecha de nacimiento no puede ser futura", status_code=400)

    edad = hoy.year - fnac.year - ((hoy.month, hoy.day) < (fnac.month, fnac.day))
    if edad < 2:
        return "infante"
    if edad < 18:
        return "menor"
    return "adulto"
