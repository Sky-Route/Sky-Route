"""Adaptadores con simuladores de SendGrid (correo) y Twilio (SMS) (API-E07 · MOD-06 · HU-015, HU-018)."""
import secrets
from typing import Any


class SendGridSimulatorAdapter:
    """Simula POST https://api.sendgrid.com/v3/mail/send."""

    disponible: bool = True

    def enviar_correo(self, destinatario: str, asunto: str, contenido: str) -> dict[str, Any]:
        if not self.disponible:
            return {
                "messageId": None,
                "destinatario": destinatario,
                "asunto": asunto,
                "estadoEntrega": "pendiente de reintento",
            }
        return {
            "messageId": f"sg_{secrets.token_hex(5)}",
            "destinatario": destinatario,
            "asunto": asunto,
            "contenido": contenido,
            "estadoEntrega": "entregado",
        }


class TwilioSimulatorAdapter:
    """Simula POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json."""

    disponible: bool = True

    def enviar_sms(self, telefono: str, mensaje: str) -> dict[str, Any]:
        if not self.disponible:
            return {
                "sid": None,
                "to": telefono,
                "estadoEntrega": "pendiente de reintento",
            }
        return {
            "sid": f"SM{secrets.token_hex(6)}",
            "to": telefono,
            "body": mensaje,
            "estadoEntrega": "entregado",
        }
