"""Repository Layer: Catálogo de vuelos, mapa de asientos y control de concurrencia de bloqueos (MOD-01)."""
import secrets
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.domain.entities.vuelo import TZ_COLOMBIA, bloqueo_esta_vencido_rn01, determinar_estado_asiento
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.database.vuelos_models import AsientoVueloModel, BloqueoAsientoModel, VueloModel

_SEAT_LOCK = threading.Lock()


class VueloRepository:
    def __init__(self, db: Session | None = None):
        Base.metadata.create_all(bind=engine)
        self._external_db = db
        self._ensure_seed()

    def _session(self) -> tuple[Session, bool]:
        if self._external_db is not None:
            return self._external_db, False
        return SessionLocal(), True

    def _ensure_seed(self) -> None:
        db, close_after = self._session()
        try:
            if db.query(VueloModel).filter_by(id_vuelo="VU-1023").first() is None:
                vuelos_seed = [
                    VueloModel(
                        id_vuelo="VU-1023",
                        aerolinea="Aerolínea Andina",
                        origen="BOG",
                        destino="MDE",
                        fecha_salida="2026-11-20",
                        salida="2026-11-20T08:15:00-05:00",
                        llegada="2026-11-20T09:10:00-05:00",
                        escalas=0,
                        clase="Económica",
                        tarifa_valor=289000,
                        tarifa_moneda="COP",
                        tarifa_vigente=True,
                        cupos_disponibles=34,
                        publicado=True,
                        aeronave_modelo="A320",
                        aeronave_capacidad=180,
                        aeronave_sincronizada=True,
                    ),
                    VueloModel(
                        id_vuelo="VU-2040",
                        aerolinea="Aerolínea Andina",
                        origen="BOG",
                        destino="CTG",
                        fecha_salida="2026-11-22",
                        salida="2026-11-22T14:00:00-05:00",
                        llegada="2026-11-22T15:30:00-05:00",
                        escalas=0,
                        clase="Económica",
                        tarifa_valor=350000,
                        tarifa_moneda="COP",
                        tarifa_vigente=True,
                        cupos_disponibles=20,
                        publicado=True,
                        aeronave_modelo=None,
                        aeronave_capacidad=0,
                        aeronave_sincronizada=False,
                    ),
                    VueloModel(
                        id_vuelo="VU-0900",
                        aerolinea="Aerolínea Andina",
                        origen="BOG",
                        destino="CLO",
                        fecha_salida="2026-10-01",
                        salida="2026-10-01T08:00:00-05:00",
                        llegada="2026-10-01T09:05:00-05:00",
                        escalas=0,
                        clase="Económica",
                        tarifa_valor=250000,
                        tarifa_moneda="COP",
                        tarifa_vigente=True,
                        cupos_disponibles=15,
                        publicado=True,
                        aeronave_modelo="A320",
                        aeronave_capacidad=180,
                        aeronave_sincronizada=True,
                    ),
                ]
                db.add_all(vuelos_seed)
                db.flush()

                asientos: list[AsientoVueloModel] = []
                letras = ["A", "B", "C", "D", "E", "F"]
                for fila in range(1, 31):
                    clase_cabina = "Ejecutiva" if fila <= 3 else "Económica"
                    for letra in letras:
                        num = f"{fila}{letra}"
                        estado_inicial = "reservado" if num == "1A" else "disponible"
                        asientos.append(
                            AsientoVueloModel(
                                id_vuelo="VU-1023",
                                numero=num,
                                clase=clase_cabina,
                                estado=estado_inicial,
                            )
                        )
                for num in ["14C", "14D", "15A"]:
                    asientos.append(
                        AsientoVueloModel(
                            id_vuelo="VU-0900",
                            numero=num,
                            clase="Económica",
                            estado="disponible",
                        )
                    )
                db.add_all(asientos)
                db.commit()
        finally:
            if close_after:
                db.close()

    def buscar_vuelos(self, origen: str, destino: str, fecha_desde: str, fecha_hasta: str) -> list[dict[str, Any]]:
        db, close_after = self._session()
        try:
            rows = (
                db.query(VueloModel)
                .filter(
                    VueloModel.origen == origen,
                    VueloModel.destino == destino,
                    VueloModel.fecha_salida >= fecha_desde,
                    VueloModel.fecha_salida <= fecha_hasta,
                )
                .all()
            )
            return [
                {
                    "idVuelo": r.id_vuelo,
                    "aerolinea": r.aerolinea,
                    "origen": r.origen,
                    "destino": r.destino,
                    "salida": r.salida,
                    "llegada": r.llegada,
                    "escalas": r.escalas,
                    "clase": r.clase,
                    "tarifa": {"valor": r.tarifa_valor, "moneda": r.tarifa_moneda},
                    "cuposDisponibles": r.cupos_disponibles,
                    "publicado": r.publicado,
                    "tarifa_vigente": r.tarifa_vigente,
                }
                for r in rows
            ]
        except Exception as exc:
            raise AppError("No fue posible consultar los itinerarios", status_code=503) from exc
        finally:
            if close_after:
                db.close()

    def obtener_vuelo(self, id_vuelo: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            r = db.query(VueloModel).filter_by(id_vuelo=id_vuelo).first()
            if not r:
                return None
            return {
                "idVuelo": r.id_vuelo,
                "aerolinea": r.aerolinea,
                "origen": r.origen,
                "destino": r.destino,
                "salida": r.salida,
                "llegada": r.llegada,
                "clase": r.clase,
                "tarifa_valor": r.tarifa_valor,
                "tarifa_moneda": r.tarifa_moneda,
                "cuposDisponibles": r.cupos_disponibles,
                "aeronave_modelo": r.aeronave_modelo,
                "aeronave_capacidad": r.aeronave_capacidad,
                "aeronave_sincronizada": r.aeronave_sincronizada,
            }
        finally:
            if close_after:
                db.close()

    def obtener_mapa_asientos(self, id_vuelo: str, ahora: datetime | None = None) -> list[dict[str, Any]]:
        db, close_after = self._session()
        try:
            asientos = db.query(AsientoVueloModel).filter_by(id_vuelo=id_vuelo).order_by(AsientoVueloModel.id).all()
            bloqueos = (
                db.query(BloqueoAsientoModel)
                .filter_by(id_vuelo=id_vuelo, estado="bloqueado")
                .all()
            )
            bloqueados_vigentes = {
                b.numero_asiento
                for b in bloqueos
                if not bloqueo_esta_vencido_rn01(b.expira_en, ahora=ahora)
            }
            cabinas_map: dict[str, list[dict[str, str]]] = {"Ejecutiva": [], "Económica": []}
            for a in asientos:
                estado_real = determinar_estado_asiento(
                    estado_base="disponible" if a.estado == "bloqueado" else a.estado,
                    tiene_bloqueo_vigente=(a.numero in bloqueados_vigentes),
                )
                cabinas_map.setdefault(a.clase, []).append({"numero": a.numero, "estado": estado_real})
            return [
                {"clase": clase, "asientos": lista}
                for clase, lista in cabinas_map.items()
                if lista
            ]
        finally:
            if close_after:
                db.close()

    def crear_bloqueo_asiento(
        self,
        id_vuelo: str,
        numero_asiento: str,
        id_sesion_compra: str,
        creado_en: str,
        expira_en: str,
        id_bloqueo_fijo: str | None = None,
    ) -> dict[str, Any]:
        """Controla concurrencia mediante candado transaccional y UPDATE condicionado al estado disponible."""
        with _SEAT_LOCK:
            db, close_after = self._session()
            try:
                vuelo = db.query(VueloModel).filter_by(id_vuelo=id_vuelo).first()
                if not vuelo:
                    raise AppError("El vuelo indicado no existe", status_code=404)

                asiento = (
                    db.query(AsientoVueloModel)
                    .filter_by(id_vuelo=id_vuelo, numero=numero_asiento)
                    .first()
                )
                if not asiento:
                    raise AppError("El asiento no existe en este vuelo", status_code=404)

                # Si tenía un bloqueo previo ya vencido y el asiento figuraba 'bloqueado', liberarlo primero
                if asiento.estado == "bloqueado":
                    bloqueos_activos = (
                        db.query(BloqueoAsientoModel)
                        .filter_by(id_vuelo=id_vuelo, numero_asiento=numero_asiento, estado="bloqueado")
                        .all()
                    )
                    alguno_vigente = False
                    for b in bloqueos_activos:
                        if bloqueo_esta_vencido_rn01(b.expira_en):
                            b.estado = "vencido"
                        else:
                            alguno_vigente = True
                    if not alguno_vigente:
                        asiento.estado = "disponible"
                        db.flush()

                stmt = (
                    update(AsientoVueloModel)
                    .where(
                        AsientoVueloModel.id_vuelo == id_vuelo,
                        AsientoVueloModel.numero == numero_asiento,
                        AsientoVueloModel.estado == "disponible",
                    )
                    .values(estado="bloqueado")
                )
                res = db.execute(stmt)
                if res.rowcount != 1:
                    db.rollback()
                    raise AppError(
                        "El asiento seleccionado ya no está disponible",
                        status_code=409,
                        data={"idVuelo": id_vuelo, "numeroAsiento": numero_asiento},
                    )

                id_blq = id_bloqueo_fijo or f"BLQ-{secrets.randbelow(90000) + 10000}"
                existente = db.query(BloqueoAsientoModel).filter_by(id_bloqueo=id_blq).first()
                if existente:
                    db.delete(existente)
                    db.flush()

                bloqueo = BloqueoAsientoModel(
                    id_bloqueo=id_blq,
                    id_vuelo=id_vuelo,
                    numero_asiento=numero_asiento,
                    id_sesion_compra=id_sesion_compra,
                    estado="bloqueado",
                    creado_en=creado_en,
                    expira_en=expira_en,
                )
                db.add(bloqueo)
                db.commit()
                return {
                    "idBloqueo": id_blq,
                    "idVuelo": id_vuelo,
                    "numeroAsiento": numero_asiento,
                    "estado": "bloqueado",
                    "expiraEn": expira_en,
                }
            finally:
                if close_after:
                    db.close()

    def obtener_bloqueo(self, id_bloqueo: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            b = db.query(BloqueoAsientoModel).filter_by(id_bloqueo=id_bloqueo).first()
            if not b:
                return None
            return {
                "idBloqueo": b.id_bloqueo,
                "idVuelo": b.id_vuelo,
                "numeroAsiento": b.numero_asiento,
                "idSesionCompra": b.id_sesion_compra,
                "estado": b.estado,
                "creadoEn": b.creado_en,
                "expiraEn": b.expira_en,
                "codigoPnr": b.codigo_pnr,
            }
        finally:
            if close_after:
                db.close()

    def confirmar_bloqueo(self, id_bloqueo: str, codigo_pnr: str, ahora: datetime | None = None) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            b = db.query(BloqueoAsientoModel).filter_by(id_bloqueo=id_bloqueo).first()
            if not b:
                raise AppError("El bloqueo indicado no existe", status_code=404, data={"idBloqueo": id_bloqueo})
            if b.estado != "bloqueado" or bloqueo_esta_vencido_rn01(b.expira_en, ahora=ahora):
                raise AppError(
                    f"El bloqueo del asiento {b.numero_asiento} venció; selecciónelo de nuevo",
                    status_code=409,
                    data={"idBloqueo": id_bloqueo},
                )
            b.estado = "confirmado"
            b.codigo_pnr = codigo_pnr
            asiento = (
                db.query(AsientoVueloModel)
                .filter_by(id_vuelo=b.id_vuelo, numero=b.numero_asiento)
                .first()
            )
            if asiento:
                asiento.estado = "reservado"
            db.commit()
            return {
                "idBloqueo": b.id_bloqueo,
                "idVuelo": b.id_vuelo,
                "numeroAsiento": b.numero_asiento,
                "estadoAsiento": "reservado",
            }
        finally:
            if close_after:
                db.close()

    def liberar_bloqueo(
        self,
        id_bloqueo: str,
        motivo: str = "vencimiento",
        ahora: datetime | None = None,
        forzar: bool = False,
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            b = db.query(BloqueoAsientoModel).filter_by(id_bloqueo=id_bloqueo).first()
            if not b:
                raise AppError("El bloqueo indicado no existe", status_code=404)

            now = ahora or datetime.now(TZ_COLOMBIA)
            if now.tzinfo is None:
                now = now.replace(tzinfo=TZ_COLOMBIA)

            if motivo == "vencimiento" and not forzar:
                if b.estado == "bloqueado" and not bloqueo_esta_vencido_rn01(b.expira_en, ahora=now):
                    raise AppError(
                        "El bloqueo aún está vigente y no puede liberarse por vencimiento",
                        status_code=409,
                        data={"idBloqueo": b.id_bloqueo, "expiraEn": b.expira_en},
                    )

            b.estado = "liberado"
            asiento = (
                db.query(AsientoVueloModel)
                .filter_by(id_vuelo=b.id_vuelo, numero=b.numero_asiento)
                .first()
            )
            if asiento:
                asiento.estado = "disponible"
            db.commit()
            return {
                "idBloqueo": b.id_bloqueo,
                "numeroAsiento": b.numero_asiento,
                "estadoAsiento": "disponible",
                "motivo": motivo,
                "fechaLiberacion": now.isoformat(timespec="seconds"),
            }
        finally:
            if close_after:
                db.close()

    def listar_bloqueos_vencidos(self, ahora: datetime | None = None) -> list[dict[str, Any]]:
        db, close_after = self._session()
        try:
            bloqueos = db.query(BloqueoAsientoModel).filter_by(estado="bloqueado").all()
            return [
                {
                    "idBloqueo": b.id_bloqueo,
                    "idVuelo": b.id_vuelo,
                    "numeroAsiento": b.numero_asiento,
                    "expiraEn": b.expira_en,
                }
                for b in bloqueos
                if bloqueo_esta_vencido_rn01(b.expira_en, ahora=ahora)
            ]
        finally:
            if close_after:
                db.close()
