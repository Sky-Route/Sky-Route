"""Service Layer: Emisión automática de factura electrónica al aprobarse pago y consulta PDF/XML (MOD-03 · HU-010)."""
from typing import Any

from app.domain.entities.factura import calcular_desglose_tributario_rn12, validar_acceso_y_estado_factura_rn12
from app.repositories.repositories.factura_repository import FacturaRepository
from app.repositories.repositories.reserva_repository import ReservaRepository
from app.services.events.event_bus import event_bus


class FacturaService:
    def __init__(
        self,
        factura_repo: FacturaRepository | None = None,
        reserva_repo: ReservaRepository | None = None,
    ):
        self.factura_repo = factura_repo or FacturaRepository()
        self.reserva_repo = reserva_repo or ReservaRepository()
        event_bus.subscribe("pago.resultado", self._on_pago_resultado)

    def _on_pago_resultado(self, evento: dict[str, Any]) -> None:
        if evento.get("tipo") != "cobro" or evento.get("estado") != "aprobada":
            return
        codigo_pnr = str(evento.get("codigoPnr") or "").strip().upper()
        monto_info = evento.get("monto") or {}
        total = int(monto_info.get("valor", 0))
        moneda = str(monto_info.get("moneda", "COP"))
        if not codigo_pnr or total <= 0:
            return
        subtotal, impuestos = calcular_desglose_tributario_rn12(total)
        self.factura_repo.emitir_y_guardar_factura(
            codigo_pnr=codigo_pnr,
            subtotal=subtotal,
            impuestos=impuestos,
            total=total,
            moneda=moneda,
        )

    def consultar_factura(self, codigo_pnr: str, apellido: str | None = None) -> dict[str, Any]:
        pnr = (codigo_pnr or "").strip().upper()
        reserva = self.reserva_repo.obtener_reserva(pnr)
        factura = self.factura_repo.obtener_factura_por_pnr(pnr)

        # Si la reserva ya está pagada pero por algún motivo no se había emitido la factura aún, emitirla
        if (
            reserva
            and factura is None
            and reserva.get("estado") in {"Confirmada", "Facturada"}
            and int(reserva.get("saldoPendiente", {}).get("valor", 0)) == 0
        ):
            total = int(reserva["total"]["valor"])
            subtotal, impuestos = calcular_desglose_tributario_rn12(total)
            factura = self.factura_repo.emitir_y_guardar_factura(
                codigo_pnr=pnr,
                subtotal=subtotal,
                impuestos=impuestos,
                total=total,
                moneda=reserva["total"]["moneda"],
            )

        validar_acceso_y_estado_factura_rn12(
            codigo_pnr=pnr,
            apellido=apellido,
            reserva=reserva,
            factura=factura,
        )
        return {
            "numeroFactura": factura["numeroFactura"],
            "codigoUnico": factura["codigoUnico"],
            "fechaEmision": factura["fechaEmision"],
            "subtotal": factura["subtotal"],
            "impuestos": factura["impuestos"],
            "total": factura["total"],
            "moneda": factura["moneda"],
            "estadoValidacion": factura["estadoValidacion"],
            "urlPdf": factura["urlPdf"],
            "urlXml": factura["urlXml"],
        }

    def reintentar_facturas_pendientes(self) -> dict[str, Any]:
        pendientes = self.factura_repo.listar_facturas_pendientes_validacion()
        facturas_resultado: list[dict[str, Any]] = []
        validadas = 0
        for fac in pendientes:
            actualizada = self.factura_repo.reintentar_validacion_factura(fac["numeroFactura"])
            if actualizada:
                facturas_resultado.append(actualizada)
                if actualizada.get("estadoValidacion") == "validada":
                    validadas += 1
        return {
            "procesadas": len(facturas_resultado),
            "validadas": validadas,
            "pendientes": len(facturas_resultado) - validadas,
            "facturas": facturas_resultado,
        }


# Instancia suscrita al bus de eventos para escuchar pago.resultado desde el arranque
factura_service_listener = FacturaService()
