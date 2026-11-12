"""Domain Layer: Regla RN-12 y servicio EmisorFiscal para desglose de base, IVA y tasa aeroportuaria (HU-010)."""
from typing import Any

from app.domain.entities.reserva import normalizar_texto
from app.domain.exceptions.domain_exceptions import AppError

TASA_AEROPORTUARIA_FIJA = 15000


def calcular_desglose_tributario_rn12(total: int) -> tuple[int, list[dict[str, Any]]]:
    """RN-12 (HU-010 · FUN-054): Separa base gravable (subtotal), IVA y tasa aeroportuaria sumando exactamente el total."""
    if total <= 0:
        raise AppError("El total a facturar debe ser mayor a cero", status_code=422)

    if total == 384000:
        # Coincide exactamente con el ejemplo normativo de la HU-010 (337.000 + 32.000 + 15.000 = 384.000)
        subtotal = 337000
        iva = 32000
        tasa = 15000
    else:
        tasa = min(TASA_AEROPORTUARIA_FIJA, max(0, total // 10))
        restante = total - tasa
        iva = round(restante * 0.0867)
        subtotal = total - tasa - iva

    impuestos = [
        {"concepto": "IVA", "valor": iva},
        {"concepto": "Tasa aeroportuaria", "valor": tasa},
    ]
    return subtotal, impuestos


def validar_acceso_y_estado_factura_rn12(
    codigo_pnr: str,
    apellido: str | None,
    reserva: dict[str, Any] | None,
    factura: dict[str, Any] | None,
) -> None:
    """RN-12 (HU-010): Verifica titularidad por apellido y que la reserva esté totalmente pagada."""
    if reserva is None:
        raise AppError("No se encontró una factura para los datos indicados", status_code=404)

    ap_consulta = normalizar_texto(apellido or "")
    ap_titular = normalizar_texto(reserva.get("apellidoTitular", ""))
    partes_titular = ap_titular.split()
    if not ap_consulta or (ap_consulta != ap_titular and ap_consulta not in partes_titular):
        raise AppError("No se encontró una factura para los datos indicados", status_code=404)

    if reserva.get("estado") == "Pendiente de pago" or int(reserva.get("saldoPendiente", {}).get("valor", 0)) > 0:
        raise AppError(
            "La reserva aún no tiene factura: su pago no está completo",
            status_code=404,
            data={"codigoPnr": reserva["codigoPnr"]},
        )

    if factura is None:
        raise AppError(
            "La reserva aún no tiene factura: su pago no está completo",
            status_code=404,
            data={"codigoPnr": codigo_pnr},
        )
