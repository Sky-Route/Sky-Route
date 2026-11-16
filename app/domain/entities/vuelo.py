"""Domain Layer: Reglas RN-01, RN-04 y RN-05 para Itinerarios, Mapa de Asientos y Bloqueos (MOD-01)."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.domain.exceptions.domain_exceptions import AppError

TZ_COLOMBIA = timezone(timedelta(hours=-5))
MINUTOS_BLOQUEO_RN01 = 15


@dataclass
class TarifaVuelo:
    valor: int
    moneda: str = "COP"


def validar_parametros_busqueda_itinerarios(
    origen: str,
    destino: str,
    fecha_desde: str,
    fecha_hasta: str,
    cupos: int,
    fecha_hoy: date | None = None,
) -> tuple[str, str, date, date]:
    """Valida formato IATA, coherencia de fechas y no fechas en el pasado (HU-002)."""
    orig = (origen or "").strip().upper()
    dest = (destino or "").strip().upper()
    if len(orig) != 3 or not orig.isalpha() or len(dest) != 3 or not dest.isalpha() or orig == dest:
        raise AppError(
            "Origen y destino deben ser códigos IATA de 3 letras y distintos entre sí",
            status_code=400,
            data={"campo": "origen"},
        )
    if cupos < 1:
        raise AppError("El número de cupos debe ser mayor o igual a 1", status_code=400, data={"campo": "cupos"})

    hoy = fecha_hoy or date(2026, 11, 10)
    try:
        f_desde = date.fromisoformat(fecha_desde)
    except Exception as exc:
        raise AppError(
            "Formato de fecha no válido o fecha anterior a hoy. Debe ser YYYY-MM-DD",
            status_code=400,
            data={"campo": "fechaDesde"},
        ) from exc

    try:
        f_hasta = date.fromisoformat(fecha_hasta)
    except Exception as exc:
        raise AppError(
            "Formato de fecha no válido o fecha anterior a hoy. Debe ser YYYY-MM-DD",
            status_code=400,
            data={"campo": "fechaHasta"},
        ) from exc

    if f_desde < hoy or f_desde > f_hasta:
        raise AppError(
            "Formato de fecha no válido o fecha anterior a hoy. Debe ser YYYY-MM-DD",
            status_code=400,
            data={"campo": "fechaDesde"},
        )

    return orig, dest, f_desde, f_hasta


def filtrar_vuelos_rn04_rn05(vuelos: list[dict[str, Any]], cupos: int) -> list[dict[str, Any]]:
    """RN-04 y RN-05: Filtra solo vuelos publicados con tarifa vigente y cupos suficientes."""
    resultado = []
    for v in vuelos:
        if not v.get("publicado", True):
            continue
        if not v.get("tarifa_vigente", True):
            continue
        if int(v.get("cuposDisponibles", 0)) < cupos:
            continue
        resultado.append(v)
    resultado.sort(key=lambda item: item["salida"])
    return resultado


def validar_vuelo_con_aeronave_rn05(vuelo: dict[str, Any] | None) -> None:
    """RN-05 (HU-003): Verifica que el vuelo exista y tenga aeronave sincronizada."""
    if vuelo is None:
        raise AppError("El vuelo indicado no existe", status_code=404)
    if not vuelo.get("aeronave_sincronizada") or not vuelo.get("aeronave_modelo"):
        raise AppError("El vuelo aún no tiene aeronave asignada", status_code=409)


def determinar_estado_asiento(estado_base: str, tiene_bloqueo_vigente: bool) -> str:
    """HU-003: Determina el estado real del asiento (disponible, bloqueado o reservado)."""
    if estado_base == "reservado":
        return "reservado"
    if tiene_bloqueo_vigente or estado_base == "bloqueado":
        return "bloqueado"
    return "disponible"


def calcular_vencimiento_bloqueo_rn01(ahora: datetime | None = None) -> tuple[str, str]:
    """RN-01 (HU-004): Calcula el instante de creación y vencimiento a 15 minutos."""
    now = ahora or datetime.now(TZ_COLOMBIA)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ_COLOMBIA)
    exp = now + timedelta(minutes=MINUTOS_BLOQUEO_RN01)
    return now.isoformat(timespec="seconds"), exp.isoformat(timespec="seconds")


def bloqueo_esta_vencido_rn01(expira_en_iso: str, ahora: datetime | None = None) -> bool:
    """RN-01 (HU-007 / HU-012): Determina si el bloqueo de 15 minutos ya superó su hora de vencimiento."""
    now = ahora or datetime.now(TZ_COLOMBIA)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ_COLOMBIA)
    exp = datetime.fromisoformat(expira_en_iso)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=TZ_COLOMBIA)
    return now >= exp
