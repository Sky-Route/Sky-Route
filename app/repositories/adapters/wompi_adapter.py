"""Adaptador con simulador de la pasarela bancaria Wompi (API-E01 · MOD-03 · HU-009, HU-013)."""
import secrets
from typing import Any


class WompiSimulatorAdapter:
    """Simula GET /v1/merchants/{llavePublica}, POST /v1/transactions y el reverso de cobros."""

    def obtener_tokens_aceptacion(self, llave_publica: str = "pub_test_skyroute") -> dict[str, str]:
        return {
            "acceptance_token": f"acc_{llave_publica}_2026",
            "presigned_personal_data_auth": f"pda_{llave_publica}_2026",
        }

    def crear_transaccion(
        self,
        amount_in_cents: int,
        currency: str,
        reference: str,
        payment_method_token: str,
        acceptance_token: str,
    ) -> dict[str, Any]:
        tok = (payment_method_token or "").strip().lower()
        wompi_id = f"wompi_{secrets.token_hex(4)}"
        if "pendiente" in tok or "timeout" in tok:
            return {
                "id": wompi_id,
                "status": "PENDING",
                "reference": reference,
                "authorization_code": None,
                "amount_in_cents": amount_in_cents,
                "currency": currency,
            }
        if "rechaz" in tok or "declin" in tok or "fail" in tok or "error" in tok:
            return {
                "id": wompi_id,
                "status": "DECLINED",
                "reference": reference,
                "authorization_code": None,
                "amount_in_cents": amount_in_cents,
                "currency": currency,
            }
        return {
            "id": wompi_id,
            "status": "APPROVED",
            "reference": reference,
            "authorization_code": f"AUT-{secrets.randbelow(900000) + 100000}",
            "amount_in_cents": amount_in_cents,
            "currency": currency,
        }

    def ejecutar_reembolso(self, id_transaccion_original: str, monto: int, moneda: str = "COP") -> dict[str, Any]:
        return {
            "idReversoPasarela": f"rev_{secrets.token_hex(4)}",
            "idTransaccionOriginal": id_transaccion_original,
            "estado": "APPROVED",
            "monto": monto,
            "moneda": moneda,
        }
