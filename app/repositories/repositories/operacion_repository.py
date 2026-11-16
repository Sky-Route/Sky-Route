"""Repository Layer: Persistencia de estatus operativo, alertas, check-in y pases de abordaje (MOD-04 y MOD-06)."""
import json
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.domain.entities.operacion import TZ_COLOMBIA
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.adapters.notificaciones_adapter import SendGridSimulatorAdapter, TwilioSimulatorAdapter
from app.repositories.database.operaciones_models import (
    AlertaPasajeroModel,
    CheckinModel,
    EstatusVueloModel,
    HistorialEstatusVueloModel,
    PaseAbordajeModel,
)


class OperacionRepository:
    def __init__(
        self,
        db: Session | None = None,
        sendgrid: SendGridSimulatorAdapter | None = None,
        twilio: TwilioSimulatorAdapter | None = None,
    ):
        Base.metadata.create_all(bind=engine)
        self._external_db = db
        self.sendgrid = sendgrid or SendGridSimulatorAdapter()
        self.twilio = twilio or TwilioSimulatorAdapter()

    def _session(self) -> tuple[Session, bool]:
        if self._external_db is not None:
            return self._external_db, False
        return SessionLocal(), True

    def obtener_o_inicializar_estatus_vuelo(self, vuelo: dict[str, Any]) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            row = db.query(EstatusVueloModel).filter_by(id_vuelo=vuelo["idVuelo"]).first()
            if not row:
                row = EstatusVueloModel(
                    id_vuelo=vuelo["idVuelo"],
                    estado="Programado",
                    puerta="B12",
                    terminal="1",
                    hora_programada_salida=vuelo["salida"],
                    hora_estimada_salida=vuelo["salida"],
                    ultima_actualizacion=vuelo["salida"],
                )
                db.add(row)
                db.commit()
                db.refresh(row)
            return {
                "idVuelo": row.id_vuelo,
                "estado": row.estado,
                "puerta": row.puerta,
                "terminal": row.terminal,
                "horaProgramadaSalida": row.hora_programada_salida,
                "horaEstimadaSalida": row.hora_estimada_salida,
                "ultimaActualizacion": row.ultima_actualizacion,
            }
        except Exception as exc:
            raise AppError("No fue posible consultar el estado del vuelo", status_code=503) from exc
        finally:
            if close_after:
                db.close()

    def guardar_cambio_estatus_vuelo(
        self,
        id_vuelo: str,
        hora_programada_salida: str,
        estado_anterior: str,
        estado_nuevo: str,
        puerta: str,
        hora_estimada_salida: str,
        fuente: str,
        observacion: str | None,
        actualizado_en: str,
        id_evento: str | None = None,
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            row = db.query(EstatusVueloModel).filter_by(id_vuelo=id_vuelo).first()
            if not row:
                row = EstatusVueloModel(
                    id_vuelo=id_vuelo,
                    estado=estado_nuevo,
                    puerta=puerta,
                    terminal="1",
                    hora_programada_salida=hora_programada_salida,
                    hora_estimada_salida=hora_estimada_salida,
                    ultima_actualizacion=actualizado_en,
                )
                db.add(row)
            else:
                row.estado = estado_nuevo
                row.puerta = puerta
                row.hora_estimada_salida = hora_estimada_salida
                row.ultima_actualizacion = actualizado_en

            evt_id = id_evento or f"EVT-{secrets.randbelow(90000) + 10000}"
            hist = HistorialEstatusVueloModel(
                id_evento=evt_id,
                id_vuelo=id_vuelo,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                puerta=puerta,
                hora_estimada_salida=hora_estimada_salida,
                fuente=fuente,
                observacion=observacion,
                actualizado_en=actualizado_en,
            )
            db.add(hist)
            db.commit()
            return {
                "idEvento": evt_id,
                "idVuelo": id_vuelo,
                "estadoAnterior": estado_anterior,
                "estadoNuevo": estado_nuevo,
                "puerta": puerta,
                "horaEstimadaSalida": hora_estimada_salida,
                "actualizadoEn": actualizado_en,
            }
        finally:
            if close_after:
                db.close()

    def alerta_ya_registrada(self, id_evento: str, id_pasajero: str) -> bool:
        db, close_after = self._session()
        try:
            return (
                db.query(AlertaPasajeroModel)
                .filter_by(id_evento=id_evento, id_pasajero=id_pasajero)
                .first()
                is not None
            )
        finally:
            if close_after:
                db.close()

    def enviar_y_guardar_alerta(
        self,
        id_evento: str,
        id_pasajero: str,
        id_vuelo: str,
        tipo_cambio: str,
        mensaje: str,
        canal: str,
        correo_destino: str,
        telefono_destino: str,
    ) -> dict[str, Any]:
        correo_limpio = (correo_destino or "").strip()
        telefono_limpio = (telefono_destino or "").strip()
        canal_final = canal

        if not correo_limpio and not telefono_limpio:
            estado_entrega = "sin destino"
        elif canal == "sms":
            if telefono_limpio:
                envio = self.twilio.enviar_sms(telefono_limpio, mensaje)
                estado_entrega = envio["estadoEntrega"]
            else:
                envio = self.sendgrid.enviar_correo(
                    destinatario=correo_limpio,
                    asunto=f"Aviso operativo de tu vuelo {id_vuelo}",
                    contenido=mensaje,
                )
                canal_final = "correo"
                estado_entrega = envio["estadoEntrega"]
        else:
            if correo_limpio:
                envio = self.sendgrid.enviar_correo(
                    destinatario=correo_limpio,
                    asunto=f"Aviso operativo de tu vuelo {id_vuelo}",
                    contenido=mensaje,
                )
                estado_entrega = envio["estadoEntrega"]
            else:
                estado_entrega = "pendiente de reintento"

            if estado_entrega != "entregado":
                if telefono_limpio:
                    envio_sms = self.twilio.enviar_sms(telefono_limpio, mensaje)
                    if envio_sms["estadoEntrega"] == "entregado":
                        canal_final = "sms"
                        estado_entrega = "entregado"
                    else:
                        estado_entrega = "pendiente de reintento"
                else:
                    estado_entrega = "pendiente de reintento"

        fecha_envio = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")
        id_alr = f"ALR-{secrets.randbelow(90000) + 10000}"

        db, close_after = self._session()
        try:
            row = AlertaPasajeroModel(
                id_alerta=id_alr,
                id_evento=id_evento,
                id_pasajero=id_pasajero,
                id_vuelo=id_vuelo,
                tipo_cambio=tipo_cambio,
                mensaje=mensaje,
                canal=canal_final,
                estado_entrega=estado_entrega,
                fecha_envio=fecha_envio,
            )
            db.add(row)
            db.commit()
            return self._alerta_to_dict(row)
        finally:
            if close_after:
                db.close()

    def listar_alertas_pasajero(self, id_pasajero: str) -> list[dict[str, Any]]:
        db, close_after = self._session()
        try:
            rows = (
                db.query(AlertaPasajeroModel)
                .filter_by(id_pasajero=id_pasajero)
                .all()
            )
            return [self._alerta_to_dict(r) for r in rows]
        finally:
            if close_after:
                db.close()

    def obtener_checkin(self, codigo_pnr: str, id_pasajero: str, id_vuelo: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = (
                db.query(CheckinModel)
                .filter_by(
                    codigo_pnr=codigo_pnr.strip().upper(),
                    id_pasajero=id_pasajero,
                    id_vuelo=id_vuelo,
                )
                .first()
            )
            if not row:
                return None
            return {
                "idCheckin": row.id_checkin,
                "codigoPnr": row.codigo_pnr,
                "idPasajero": row.id_pasajero,
                "idVuelo": row.id_vuelo,
                "estadoPasajero": row.estado_pasajero,
                "asiento": row.asiento,
                "idPaseAbordaje": row.id_pase_abordaje,
            }
        finally:
            if close_after:
                db.close()

    def guardar_checkin_y_pase(
        self,
        codigo_pnr: str,
        id_pasajero: str,
        nombre_pasajero: str,
        correo_pasajero: str,
        id_vuelo: str,
        vuelo_info: dict[str, Any],
        asiento: str,
        codigo_qr: str,
        fecha_checkin: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sufijo = secrets.randbelow(9000) + 1000
        id_chk = f"CHK-{sufijo}"
        id_pab = f"PAB-{sufijo}"
        url_pdf = f"https://api.skyroute.example/pases/{id_pab}.pdf"

        db, close_after = self._session()
        try:
            chk_row = CheckinModel(
                id_checkin=id_chk,
                codigo_pnr=codigo_pnr.strip().upper(),
                id_pasajero=id_pasajero,
                id_vuelo=id_vuelo,
                asiento=asiento,
                estado_pasajero="Check-in",
                id_pase_abordaje=id_pab,
                fecha_checkin=fecha_checkin,
            )
            pab_row = PaseAbordajeModel(
                id_pase_abordaje=id_pab,
                codigo_pnr=codigo_pnr.strip().upper(),
                id_pasajero=id_pasajero,
                nombre_pasajero=nombre_pasajero,
                id_vuelo=id_vuelo,
                vuelo_json=json.dumps(vuelo_info),
                asiento=asiento,
                codigo_qr=codigo_qr,
                url_pdf=url_pdf,
                enviado_a=correo_pasajero,
                estado_envio="pendiente",
                version=1,
            )
            db.add(chk_row)
            db.add(pab_row)
            db.commit()
            db.refresh(pab_row)
            return (
                {
                    "idCheckin": id_chk,
                    "codigoPnr": chk_row.codigo_pnr,
                    "idPasajero": id_pasajero,
                    "estadoPasajero": "Check-in",
                    "asiento": asiento,
                    "idPaseAbordaje": id_pab,
                },
                self._pase_to_dict(pab_row),
            )
        finally:
            if close_after:
                db.close()

    def actualizar_envio_pase(self, id_pase_abordaje: str, estado_envio: str) -> None:
        db, close_after = self._session()
        try:
            row = db.query(PaseAbordajeModel).filter_by(id_pase_abordaje=id_pase_abordaje).first()
            if row:
                row.estado_envio = estado_envio
                db.commit()
        finally:
            if close_after:
                db.close()

    def obtener_pase_abordaje(self, codigo_pnr: str, id_pasajero: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = (
                db.query(PaseAbordajeModel)
                .filter_by(codigo_pnr=codigo_pnr.strip().upper(), id_pasajero=id_pasajero)
                .first()
            )
            return self._pase_to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    @staticmethod
    def _alerta_to_dict(row: AlertaPasajeroModel) -> dict[str, Any]:
        return {
            "idAlerta": row.id_alerta,
            "idVuelo": row.id_vuelo,
            "tipoCambio": row.tipo_cambio,
            "mensaje": row.mensaje,
            "canal": row.canal,
            "estadoEntrega": row.estado_entrega,
            "fechaEnvio": row.fecha_envio,
        }

    @staticmethod
    def _pase_to_dict(row: PaseAbordajeModel) -> dict[str, Any]:
        return {
            "idPaseAbordaje": row.id_pase_abordaje,
            "pasajero": row.nombre_pasajero,
            "vuelo": json.loads(row.vuelo_json),
            "asiento": row.asiento,
            "codigoQR": row.codigo_qr,
            "urlPdf": row.url_pdf,
            "enviadoA": row.enviado_a,
            "estadoEnvio": row.estado_envio,
        }
