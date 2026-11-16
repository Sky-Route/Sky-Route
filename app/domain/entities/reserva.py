"""Domain Layer: Reglas RN-01, RN-06, RN-07, RN-10, RN-12 y RN-15 para Reservas y Cobros (HU-007 a HU-013)."""
import secrets
import string
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.exceptions.domain_exceptions import AppError

TZ_COLOMBIA = timezone(timedelta(hours=-5))
PENALIDAD_ESTANDAR_RN07 = 60000


def normalizar_texto(texto: str) -> str:
    """Elimina tildes y pasa a minúsculas para comparar apellidos (HU-011 / HU-013)."""
    nfkd = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def generar_codigo_pnr_unico(existentes: set[str]) -> str:
    """RN-01 / HU-007: Genera un PNR alfanumérico único de 6 caracteres en mayúsculas."""
    alfabeto = string.ascii_uppercase + string.digits
    for _ in range(100):
        candidato = "".join(secrets.choice(alfabeto) for _ in range(6))
        if candidato not in existentes:
            return candidato
    raise AppError("No fue posible generar un código PNR único", status_code=500)


def validar_reglas_creacion_reserva_rn06(pasajeros_detalle: list[dict[str, Any]]) -> None:
    """RN-06 (HU-007): Verifica que haya pasajeros y que ningún menor viaje sin un adulto en el mismo PNR."""
    if not pasajeros_detalle:
        raise AppError("La reserva debe incluir al menos un pasajero", status_code=400)

    hay_adulto = any(p.get("tipoPasajero") == "adulto" for p in pasajeros_detalle)
    hay_menor_o_infante = any(p.get("tipoPasajero") in {"menor", "infante"} for p in pasajeros_detalle)
    if hay_menor_o_infante and not hay_adulto:
        raise AppError(
            "Un menor de edad debe viajar con un adulto en la misma reserva",
            status_code=422,
        )


def validar_consulta_reserva_pnr(codigo_pnr: str, apellido: str | None, reserva: dict[str, Any] | None) -> None:
    """HU-011: Valida formato PNR de 6 caracteres y coincidencia con el apellido del titular."""
    pnr = (codigo_pnr or "").strip().upper()
    if len(pnr) != 6 or not pnr.isalnum():
        raise AppError("El código de reserva debe tener 6 caracteres alfanuméricos", status_code=400)

    if reserva is None:
        raise AppError("No se encontró una reserva con los datos indicados", status_code=404)

    if apellido is not None:
        ap_consulta = normalizar_texto(apellido)
        ap_titular = normalizar_texto(reserva.get("apellidoTitular", ""))
        partes_titular = ap_titular.split()
        if not ap_consulta or (ap_consulta != ap_titular and ap_consulta not in partes_titular):
            raise AppError("No se encontró una reserva con los datos indicados", status_code=404)


def validar_y_calcular_equipaje_rn10(
    reserva: dict[str, Any] | None,
    id_pasajero: str,
    opcion_catalogo: dict[str, Any] | None,
    peso_kg: int,
    piezas: int,
) -> tuple[int, int, int]:
    """RN-10 (HU-008): Solo reservas vigentes admiten equipaje; valida peso máximo y recalcula total y saldo."""
    if reserva is None:
        raise AppError("La reserva indicada no existe", status_code=404)

    if reserva["estado"] == "Cancelada":
        raise AppError("No se pueden agregar servicios a una reserva cancelada", status_code=409)

    ids_pasajeros = {p["idPasajero"] for p in reserva.get("pasajeros", [])}
    if id_pasajero not in ids_pasajeros:
        raise AppError("El pasajero no pertenece a la reserva indicada", status_code=404)

    if opcion_catalogo is None:
        raise AppError("El tipo de equipaje solicitado no existe en el catálogo", status_code=400)

    max_kg = int(opcion_catalogo["pesoMaximoKg"])
    if peso_kg > max_kg:
        raise AppError(
            f"El peso por pieza supera el máximo permitido de {max_kg} kg",
            status_code=422,
            data={"pesoKg": peso_kg, "maximoKg": max_kg},
        )

    if piezas < 1 or peso_kg < 1:
        raise AppError("El peso y el número de piezas deben ser mayores a cero", status_code=400)

    cargo = int(opcion_catalogo["precio"]["valor"]) * piezas
    nuevo_total = int(reserva["total"]["valor"]) + cargo
    nuevo_saldo = int(reserva["saldoPendiente"]["valor"]) + cargo
    return cargo, nuevo_total, nuevo_saldo


def validar_cobro_reserva_rn10_rn12(reserva: dict[str, Any] | None, monto: int) -> None:
    """RN-10 y RN-12 (HU-009): La reserva debe estar vigente con saldo pendiente y el monto igual al saldo."""
    if reserva is None:
        raise AppError("La reserva indicada no existe", status_code=404)

    if reserva["estado"] == "Cancelada":
        raise AppError("No se puede cobrar una reserva cancelada", status_code=409)

    saldo = int(reserva["saldoPendiente"]["valor"])
    if reserva["estado"] not in {"Pendiente de pago", "Confirmada"} or saldo <= 0:
        raise AppError("La reserva no tiene saldo pendiente de pago", status_code=409)

    if int(monto) != saldo:
        raise AppError("El monto no coincide con el saldo pendiente de la reserva", status_code=422)


def reserva_pendiente_esta_vencida_rn10(reserva: dict[str, Any], ahora: datetime | None = None) -> bool:
    """RN-10 (HU-012): Solo se cancelan por vencimiento las reservas en estado 'Pendiente de pago' cuyo plazo venció."""
    if reserva.get("estado") != "Pendiente de pago":
        return False
    vence_en = reserva.get("venceEn")
    if not vence_en:
        return False
    now = ahora or datetime.now(TZ_COLOMBIA)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ_COLOMBIA)
    vence_dt = datetime.fromisoformat(vence_en)
    if vence_dt.tzinfo is None:
        vence_dt = vence_dt.replace(tzinfo=TZ_COLOMBIA)
    return now >= vence_dt


def evaluar_cancelacion_y_penalidad_rn07_rn10(
    reserva: dict[str, Any] | None,
    apellido: str,
    ahora: datetime | None = None,
    tarifa_reembolsable: bool = True,
) -> tuple[bool, int, int]:
    """RN-07 y RN-10 (HU-013): Valida estado cancelable, fecha de salida del vuelo y calcula penalidad y reembolso."""
    if reserva is None:
        raise AppError("No se encontró una reserva con los datos indicados", status_code=404)

    if reserva["estado"] == "Cancelada":
        raise AppError(
            "La reserva ya está cancelada",
            status_code=409,
            data={"codigoPnr": reserva["codigoPnr"], "estado": "Cancelada"},
        )

    validar_consulta_reserva_pnr(reserva["codigoPnr"], apellido, reserva)

    now = ahora or datetime.now(TZ_COLOMBIA)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ_COLOMBIA)
    salida_str = reserva["vuelo"]["salida"]
    salida_dt = datetime.fromisoformat(salida_str)
    if salida_dt.tzinfo is None:
        salida_dt = salida_dt.replace(tzinfo=TZ_COLOMBIA)

    if now >= salida_dt:
        raise AppError("No se puede cancelar una reserva después de la salida del vuelo", status_code=422)

    total_pagado = int(reserva["total"]["valor"]) - int(reserva["saldoPendiente"]["valor"])
    if reserva["estado"] == "Pendiente de pago" or total_pagado <= 0 or not tarifa_reembolsable:
        return False, 0, 0

    penalidad = min(PENALIDAD_ESTANDAR_RN07, total_pagado)
    monto_reembolso = max(0, total_pagado - penalidad)
    return monto_reembolso > 0, penalidad, monto_reembolso


def validar_segundo_aprobador_reembolso_rn15(
    reembolso: dict[str, Any] | None,
    aprobador: str,
    decision: str,
) -> str:
    """RN-15 (HU-013): Exige doble control (aprobador distinto de quien solicitó) antes de ejecutar el reembolso."""
    if reembolso is None:
        raise AppError("La orden de reembolso indicada no existe", status_code=404)
    if reembolso["estado"] != "Pendiente de aprobación":
        raise AppError("El reembolso ya fue procesado anteriormente", status_code=409)

    aprob = (aprobador or "").strip()
    if not aprob:
        raise AppError("Debe indicar el usuario aprobador del reembolso", status_code=400)
    if aprob.lower() == (reembolso.get("solicitadoPor") or "").strip().lower():
        raise AppError(
            "El segundo aprobador debe ser distinto a quien originó la solicitud (RN-15)",
            status_code=422,
        )

    dec = (decision or "").strip().lower()
    if dec not in {"aprobar", "rechazar"}:
        raise AppError("La decisión debe ser 'aprobar' o 'rechazar'", status_code=400)
    return "ejecutado" if dec == "aprobar" else "rechazado"
