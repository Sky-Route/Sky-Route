"""Repository Layer: Persistencia de reservas, equipaje adicional, transacciones y reembolsos (MOD-02 y MOD-03)."""
import json
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.domain.entities.reserva import TZ_COLOMBIA
from app.repositories.adapters.wompi_adapter import WompiSimulatorAdapter
from app.repositories.database.reservas_models import (
    CatalogoEquipajeModel,
    EquipajeReservaModel,
    ReembolsoModel,
    ReservaModel,
    TransaccionPagoModel,
)


class ReservaRepository:
    def __init__(self, db: Session | None = None, wompi_adapter: WompiSimulatorAdapter | None = None):
        Base.metadata.create_all(bind=engine)
        self._external_db = db
        self.wompi = wompi_adapter or WompiSimulatorAdapter()
        self._ensure_seed()

    def _session(self) -> tuple[Session, bool]:
        if self._external_db is not None:
            return self._external_db, False
        return SessionLocal(), True

    def _ensure_seed(self) -> None:
        db, close_after = self._session()
        try:
            if db.query(CatalogoEquipajeModel).count() == 0:
                db.add_all(
                    [
                        CatalogoEquipajeModel(
                            tipo="cabina",
                            peso_maximo_kg=10,
                            precio_valor=55000,
                            moneda="COP",
                        ),
                        CatalogoEquipajeModel(
                            tipo="bodega",
                            peso_maximo_kg=23,
                            precio_valor=95000,
                            moneda="COP",
                        ),
                    ]
                )
                db.commit()
        finally:
            if close_after:
                db.close()

    def codigos_pnr_existentes(self) -> set[str]:
        db, close_after = self._session()
        try:
            return {r.codigo_pnr for r in db.query(ReservaModel.codigo_pnr).all()}
        finally:
            if close_after:
                db.close()

    def guardar_reserva(
        self,
        codigo_pnr: str,
        id_vuelo: str,
        estado: str,
        vence_en: str | None,
        apellido_titular: str,
        vuelo: dict[str, Any],
        pasajeros: list[dict[str, Any]],
        total_valor: int,
        saldo_pendiente: int,
        moneda: str = "COP",
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            existente = db.query(ReservaModel).filter_by(codigo_pnr=codigo_pnr).first()
            if existente:
                db.delete(existente)
                db.flush()
            row = ReservaModel(
                codigo_pnr=codigo_pnr,
                id_vuelo=id_vuelo,
                estado=estado,
                vence_en=vence_en,
                apellido_titular=apellido_titular,
                vuelo_json=json.dumps(vuelo),
                pasajeros_json=json.dumps(pasajeros),
                servicios_json="[]",
                total_valor=total_valor,
                saldo_pendiente=saldo_pendiente,
                moneda=moneda,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)
        finally:
            if close_after:
                db.close()

    def obtener_reserva(self, codigo_pnr: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(ReservaModel).filter_by(codigo_pnr=codigo_pnr.strip().upper()).first()
            return self._to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    def listar_reservas_por_estado(self, estado: str) -> list[dict[str, Any]]:
        db, close_after = self._session()
        try:
            rows = db.query(ReservaModel).filter_by(estado=estado).all()
            return [self._to_dict(r) for r in rows]
        finally:
            if close_after:
                db.close()

    def actualizar_estado_reserva(
        self,
        codigo_pnr: str,
        nuevo_estado: str,
        saldo_pendiente: int | None = None,
        vence_en: str | None = "__keep__",
        motivo_cancelacion: str | None = None,
    ) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(ReservaModel).filter_by(codigo_pnr=codigo_pnr.strip().upper()).first()
            if not row:
                return None
            row.estado = nuevo_estado
            if saldo_pendiente is not None:
                row.saldo_pendiente = saldo_pendiente
            if vence_en != "__keep__":
                row.vence_en = vence_en
            if motivo_cancelacion is not None:
                row.motivo_cancelacion = motivo_cancelacion
            db.commit()
            db.refresh(row)
            return self._to_dict(row)
        finally:
            if close_after:
                db.close()

    def listar_catalogo_equipaje(self) -> list[dict[str, Any]]:
        db, close_after = self._session()
        try:
            rows = db.query(CatalogoEquipajeModel).order_by(CatalogoEquipajeModel.id).all()
            return [
                {
                    "tipo": r.tipo,
                    "pesoMaximoKg": r.peso_maximo_kg,
                    "precio": {"valor": r.precio_valor, "moneda": r.moneda},
                }
                for r in rows
            ]
        finally:
            if close_after:
                db.close()

    def obtener_opcion_equipaje(self, tipo: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            r = db.query(CatalogoEquipajeModel).filter_by(tipo=(tipo or "").strip().lower()).first()
            if not r:
                return None
            return {
                "tipo": r.tipo,
                "pesoMaximoKg": r.peso_maximo_kg,
                "precio": {"valor": r.precio_valor, "moneda": r.moneda},
            }
        finally:
            if close_after:
                db.close()

    def agregar_equipaje_reserva(
        self,
        codigo_pnr: str,
        id_pasajero: str,
        tipo: str,
        peso_kg: int,
        piezas: int,
        cargo_valor: int,
        nuevo_total: int,
        nuevo_saldo: int,
        moneda: str = "COP",
        id_equipaje_fijo: str | None = None,
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            id_eqp = id_equipaje_fijo or f"EQP-{secrets.randbelow(9000) + 1000}"
            row_eqp = EquipajeReservaModel(
                id_equipaje=id_eqp,
                codigo_pnr=codigo_pnr,
                id_pasajero=id_pasajero,
                tipo=tipo,
                peso_kg=peso_kg,
                piezas=piezas,
                cargo_valor=cargo_valor,
                moneda=moneda,
            )
            db.add(row_eqp)

            res = db.query(ReservaModel).filter_by(codigo_pnr=codigo_pnr).first()
            if res:
                servicios = json.loads(res.servicios_json or "[]")
                servicios.append(
                    {
                        "idEquipaje": id_eqp,
                        "idPasajero": id_pasajero,
                        "tipo": f"equipaje {tipo}",
                        "pesoKg": peso_kg,
                        "piezas": piezas,
                        "cargo": {"valor": cargo_valor, "moneda": moneda},
                    }
                )
                res.servicios_json = json.dumps(servicios)
                res.total_valor = nuevo_total
                res.saldo_pendiente = nuevo_saldo
            db.commit()
            return {
                "idEquipaje": id_eqp,
                "idPasajero": id_pasajero,
                "tipo": tipo,
                "pesoKg": peso_kg,
                "cargo": {"valor": cargo_valor, "moneda": moneda},
                "totalReserva": {"valor": nuevo_total, "moneda": moneda},
                "saldoPendiente": {"valor": nuevo_saldo, "moneda": moneda},
            }
        finally:
            if close_after:
                db.close()

    def obtener_transaccion_por_idempotencia(self, idempotency_key: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(TransaccionPagoModel).filter_by(idempotency_key=idempotency_key).first()
            return self._tx_to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    def obtener_ultima_transaccion_aprobada(self, codigo_pnr: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = (
                db.query(TransaccionPagoModel)
                .filter_by(codigo_pnr=codigo_pnr, estado="aprobada")
                .order_by(TransaccionPagoModel.fecha.desc())
                .first()
            )
            return self._tx_to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    def procesar_y_guardar_transaccion(
        self,
        idempotency_key: str,
        codigo_pnr: str,
        monto: int,
        moneda: str,
        token_medio_pago: str,
        concepto: str,
        id_transaccion_fijo: str | None = None,
    ) -> dict[str, Any]:
        tokens_comercio = self.wompi.obtener_tokens_aceptacion()
        wompi_res = self.wompi.crear_transaccion(
            amount_in_cents=monto * 100,
            currency=moneda,
            reference=codigo_pnr,
            payment_method_token=token_medio_pago,
            acceptance_token=tokens_comercio["acceptance_token"],
        )
        status_map = {
            "APPROVED": "aprobada",
            "DECLINED": "rechazada",
            "PENDING": "pendiente",
        }
        estado_tx = status_map.get(wompi_res["status"], "rechazada")
        id_tx = id_transaccion_fijo or f"TRX-{secrets.randbelow(90000) + 10000}"
        fecha_iso = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")

        db, close_after = self._session()
        try:
            row = TransaccionPagoModel(
                id_transaccion=id_tx,
                idempotency_key=idempotency_key,
                codigo_pnr=codigo_pnr,
                estado=estado_tx,
                codigo_autorizacion=wompi_res.get("authorization_code"),
                monto_valor=monto,
                moneda=moneda,
                token_medio_pago=token_medio_pago,
                concepto=concepto,
                fecha=fecha_iso,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._tx_to_dict(row)
        finally:
            if close_after:
                db.close()

    def crear_orden_reembolso(
        self,
        id_transaccion_original: str,
        codigo_pnr: str,
        penalidad_valor: int,
        monto_reembolso: int,
        motivo: str,
        moneda: str = "COP",
        solicitado_por: str = "sistema-reservas",
        id_reembolso_fijo: str | None = None,
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            id_rem = id_reembolso_fijo or f"REM-{secrets.randbelow(9000) + 1000}"
            if db.query(ReembolsoModel).filter_by(id_reembolso=id_rem).first():
                id_rem = f"REM-{secrets.randbelow(90000) + 10000}"
            fecha_sol = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")
            row = ReembolsoModel(
                id_reembolso=id_rem,
                id_transaccion_original=id_transaccion_original,
                codigo_pnr=codigo_pnr,
                estado="Pendiente de aprobación",
                penalidad_valor=penalidad_valor,
                monto_reembolso=monto_reembolso,
                moneda=moneda,
                motivo=motivo,
                solicitado_por=solicitado_por,
                fecha_solicitud=fecha_sol,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._rem_to_dict(row)
        finally:
            if close_after:
                db.close()

    def obtener_reembolso(self, id_reembolso: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(ReembolsoModel).filter_by(id_reembolso=id_reembolso).first()
            return self._rem_to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    def resolver_reembolso(
        self,
        id_reembolso: str,
        nuevo_estado: str,
        aprobador: str,
        observacion: str | None = None,
    ) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(ReembolsoModel).filter_by(id_reembolso=id_reembolso).first()
            if not row:
                return None
            if nuevo_estado == "ejecutado":
                self.wompi.ejecutar_reembolso(
                    id_transaccion_original=row.id_transaccion_original,
                    monto=row.monto_reembolso,
                    moneda=row.moneda,
                )
            row.estado = nuevo_estado
            row.aprobado_por = aprobador
            row.observacion_aprobacion = observacion
            row.fecha_ejecucion = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")
            db.commit()
            db.refresh(row)
            return self._rem_to_dict(row)
        finally:
            if close_after:
                db.close()

    @staticmethod
    def _to_dict(row: ReservaModel) -> dict[str, Any]:
        return {
            "codigoPnr": row.codigo_pnr,
            "idVuelo": row.id_vuelo,
            "estado": row.estado,
            "venceEn": row.vence_en,
            "apellidoTitular": row.apellido_titular,
            "vuelo": json.loads(row.vuelo_json),
            "pasajeros": json.loads(row.pasajeros_json),
            "servicios": json.loads(row.servicios_json or "[]"),
            "total": {"valor": row.total_valor, "moneda": row.moneda},
            "saldoPendiente": {"valor": row.saldo_pendiente, "moneda": row.moneda},
            "motivoCancelacion": row.motivo_cancelacion,
        }

    @staticmethod
    def _tx_to_dict(row: TransaccionPagoModel) -> dict[str, Any]:
        return {
            "idTransaccion": row.id_transaccion,
            "idempotencyKey": row.idempotency_key,
            "codigoPnr": row.codigo_pnr,
            "estado": row.estado,
            "codigoAutorizacion": row.codigo_autorizacion,
            "monto": {"valor": row.monto_valor, "moneda": row.moneda},
            "fecha": row.fecha,
        }

    @staticmethod
    def _rem_to_dict(row: ReembolsoModel) -> dict[str, Any]:
        return {
            "idReembolso": row.id_reembolso,
            "idTransaccionOriginal": row.id_transaccion_original,
            "codigoPnr": row.codigo_pnr,
            "estado": row.estado,
            "penalidad": {"valor": row.penalidad_valor, "moneda": row.moneda},
            "montoReembolso": {"valor": row.monto_reembolso, "moneda": row.moneda},
            "motivo": row.motivo,
            "solicitadoPor": row.solicitado_por,
            "aprobadoPor": row.aprobado_por,
            "fecha": row.fecha_solicitud,
            "fechaEjecucion": row.fecha_ejecucion,
        }
