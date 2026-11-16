"""Adaptador con simulador de facturación electrónica Alegra / DIAN (API-E02 · MOD-03 · HU-010)."""
import hashlib
import secrets
from typing import Any


class AlegraSimulatorAdapter:
    """Simula POST /api/v1/invoices y POST /api/v1/invoices/stamp de Alegra."""

    entidad_fiscal_disponible: bool = True

    def emitir_y_timbrar_factura(
        self,
        numero_factura: str,
        codigo_pnr: str,
        subtotal: int,
        impuestos: list[dict[str, Any]],
        total: int,
        moneda: str = "COP",
    ) -> dict[str, Any]:
        cufe_seed = f"{numero_factura}|{codigo_pnr}|{total}|{secrets.token_hex(4)}"
        codigo_unico = hashlib.sha256(cufe_seed.encode("utf-8")).hexdigest()[:32]
        if not self.entidad_fiscal_disponible:
            return {
                "alegraId": None,
                "codigoUnico": codigo_unico,
                "estadoValidacion": "pendiente de validación",
                "urlPdf": f"https://api.skyroute.example/facturas/{numero_factura}.pdf",
                "urlXml": f"https://api.skyroute.example/facturas/{numero_factura}.xml",
            }
        return {
            "alegraId": f"ALG-{secrets.randbelow(90000) + 10000}",
            "codigoUnico": codigo_unico,
            "estadoValidacion": "validada",
            "urlPdf": f"https://api.skyroute.example/facturas/{numero_factura}.pdf",
            "urlXml": f"https://api.skyroute.example/facturas/{numero_factura}.xml",
        }
