"""Domain Layer: Reglas de transición de estatus de vuelo (HU-014), canal de alertas RN-27 (HU-015),
ventana de check-in RN-16 (HU-017) y firma criptográfica de código QR para pase de abordaje (HU-018)."""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.domain.exceptions.domain_exceptions import AppError

TZ_COLOMBIA = timezone(timedelta(hours=-5))

TRANSICIONES_VALIDAS_VUELO: dict[str, set[str]] = {
    "Programado": {"Programado", "En sala", "Retrasado", "Cancelado"},
    "En sala": {"En sala", "Embarcando", "Retrasado", "Cancelado"},
    "Retrasado": {"Retrasado", "En sala", "Embarcando", "Cancelado"},
    "Embarcando": {"Embarcando", "Cerrado"},
    "Cerrado": {"Cerrado", "En vuelo"},
    "En vuelo": {"En vuelo", "Arribado"},
    "Cancelado": set(),
    "Arribado": set(),
}


def validar_permiso_operaciones_hu014(alcance_token: list[str] | None) -> None:
    """HU-014: Solo un usuario/aplicación con rol o alcance de operaciones ('vuelos:escribir') puede actualizar el estado."""
    scopes = set(alcance_token or [])
    if "vuelos:escribir" not in scopes and "operaciones:escribir" not in scopes and "*" not in scopes:
        raise AppError("No tiene permiso para actualizar el estado del vuelo", status_code=403)


def validar_transicion_estatus_vuelo_hu014(
    id_vuelo: str,
    estado_actual: str,
    estado_nuevo: str,
) -> None:
    """HU-014: Valida que la transición desde estado_actual hacia estado_nuevo sea permitida."""
    permitidos = TRANSICIONES_VALIDAS_VUELO.get(estado_actual, set())
    if estado_nuevo not in permitidos:
        raise AppError(
            f"No se puede pasar de '{estado_actual}' a '{estado_nuevo}'",
            status_code=409,
            data={"idVuelo": id_vuelo, "estadoActual": estado_actual},
        )


def construir_alerta_operativa_rn27(
    id_vuelo: str,
    origen: str,
    destino: str,
    estado_nuevo: str,
    puerta: str,
    hora_estimada_salida: str,
    canal_preferido: str | None = None,
) -> tuple[str, str]:
    """RN-27 (HU-015): Arma el mensaje operativo y determina el canal preferido del pasajero (por defecto correo)."""
    canal = (canal_preferido or "correo").strip().lower()
    if canal not in {"correo", "sms"}:
        canal = "correo"

    try:
        dt = datetime.fromisoformat(hora_estimada_salida)
        hh_mm = dt.strftime("%H:%M")
    except Exception:
        hh_mm = hora_estimada_salida[11:16] if len(hora_estimada_salida) >= 16 else hora_estimada_salida

    if estado_nuevo == "Cancelado":
        mensaje = f"Tu vuelo {id_vuelo} {origen}-{destino} ha sido cancelado."
    else:
        mensaje = f"Tu vuelo {id_vuelo} {origen}-{destino} sale a las {hh_mm} por la puerta {puerta}."
    return mensaje, canal


def calcular_ventana_checkin_rn16(
    hora_salida_iso: str,
    ahora: datetime,
) -> dict[str, str]:
    """RN-16 (HU-017): Calcula la apertura (24 h antes) y el cierre (2 h antes) de la ventana de check-in."""
    salida_dt = datetime.fromisoformat(hora_salida_iso)
    if salida_dt.tzinfo is None:
        salida_dt = salida_dt.replace(tzinfo=TZ_COLOMBIA)

    now = ahora if ahora.tzinfo is not None else ahora.replace(tzinfo=TZ_COLOMBIA)
    apertura_dt = salida_dt - timedelta(hours=24)
    cierre_dt = salida_dt - timedelta(hours=2)

    if now < apertura_dt:
        estado_ventana = "en espera de apertura"
    elif now <= cierre_dt:
        estado_ventana = "abierta"
    else:
        estado_ventana = "cerrada"

    return {
        "estadoVentana": estado_ventana,
        "aperturaVentana": apertura_dt.isoformat(timespec="seconds"),
        "cierreVentana": cierre_dt.isoformat(timespec="seconds"),
    }


def validar_checkin_en_linea_rn16(
    reserva: dict[str, Any] | None,
    id_pasajero: str,
    id_vuelo: str,
    hora_salida_iso: str,
    ahora: datetime,
) -> dict[str, Any]:
    """RN-16 (HU-017): Verifica reserva pagada, pertenencia del pasajero y ventana entre 24 y 2 horas antes."""
    if reserva is None:
        raise AppError("La reserva indicada no existe", status_code=404)

    if reserva.get("idVuelo") != id_vuelo:
        raise AppError("El vuelo indicado no coincide con el de la reserva", status_code=422)

    if reserva.get("estado") not in {"Confirmada", "Facturada"} or int(reserva.get("saldoPendiente", {}).get("valor", 0)) > 0:
        raise AppError("La reserva debe estar pagada para hacer check-in", status_code=422)

    pasajero_en_reserva = next(
        (p for p in reserva.get("pasajeros", []) if p.get("idPasajero") == id_pasajero),
        None,
    )
    if pasajero_en_reserva is None or not pasajero_en_reserva.get("asiento"):
        raise AppError("El pasajero no pertenece a la reserva o no tiene asiento asignado", status_code=404)

    ventana = calcular_ventana_checkin_rn16(hora_salida_iso=hora_salida_iso, ahora=ahora)
    if ventana["estadoVentana"] != "abierta":
        raise AppError(
            "El check-in en línea está disponible entre 24 y 2 horas antes de la salida",
            status_code=422,
            data={
                "aperturaVentana": ventana["aperturaVentana"],
                "cierreVentana": ventana["cierreVentana"],
            },
        )
    return pasajero_en_reserva


def generar_codigo_qr_firmado_hu018(
    codigo_pnr: str,
    id_pasajero: str,
    id_vuelo: str,
    asiento: str,
) -> str:
    """HU-018: Genera la cadena del código QR con firma HMAC-SHA256 verificable en puerta."""
    base_str = f"SR1|{codigo_pnr}|{id_pasajero}|{id_vuelo}|{asiento}"
    firma = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        base_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"{base_str}|firma:{firma}"


def verificar_firma_codigo_qr_hu018(codigo_qr: str) -> bool:
    """HU-018: Verifica que la firma criptográfica de un código QR de pase de abordaje sea auténtica."""
    partes = (codigo_qr or "").split("|")
    if len(partes) != 6 or not partes[5].startswith("firma:"):
        return False
    esperado = generar_codigo_qr_firmado_hu018(partes[1], partes[2], partes[3], partes[4])
    return hmac.compare_digest(codigo_qr, esperado)
