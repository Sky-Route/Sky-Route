"""Repository Layer: Persistencia de consentimientos (MOD-07 · HU-005) y pasajeros (MOD-02 · HU-006)."""
import json
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.domain.entities.cliente import TZ_COLOMBIA
from app.repositories.database.clientes_models import ConsentimientoModel, PasajeroModel


class ClienteRepository:
    def __init__(self, db: Session | None = None):
        Base.metadata.create_all(bind=engine)
        self._external_db = db

    def _session(self) -> tuple[Session, bool]:
        if self._external_db is not None:
            return self._external_db, False
        return SessionLocal(), True

    def guardar_consentimiento(
        self,
        tipo_documento: str,
        numero_documento: str,
        finalidades: list[dict[str, str]],
        canal: str,
        puede_continuar: bool,
        id_consentimiento_fijo: str | None = None,
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            prev_count = (
                db.query(ConsentimientoModel)
                .filter_by(tipo_documento=tipo_documento, numero_documento=numero_documento)
                .count()
            )
            id_con = id_consentimiento_fijo or f"CON-{secrets.randbelow(9000) + 1000}"
            if db.query(ConsentimientoModel).filter_by(id_consentimiento=id_con).first():
                id_con = f"CON-{secrets.randbelow(90000) + 10000}"
            fecha_reg = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")
            row = ConsentimientoModel(
                id_consentimiento=id_con,
                tipo_documento=tipo_documento,
                numero_documento=numero_documento,
                finalidades_json=json.dumps(finalidades),
                canal=canal,
                fecha_registro=fecha_reg,
                puede_continuar_compra=puede_continuar,
                version=prev_count + 1,
            )
            db.add(row)
            db.commit()
            return {
                "idConsentimiento": id_con,
                "titular": {"tipoDocumento": tipo_documento, "numeroDocumento": numero_documento},
                "finalidades": finalidades,
                "canal": canal,
                "fechaRegistro": fecha_reg,
                "puedeContinuarCompra": puede_continuar,
            }
        finally:
            if close_after:
                db.close()

    def obtener_consentimiento(self, id_consentimiento: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(ConsentimientoModel).filter_by(id_consentimiento=id_consentimiento).first()
            if not row:
                return None
            return {
                "idConsentimiento": row.id_consentimiento,
                "titular": {"tipoDocumento": row.tipo_documento, "numeroDocumento": row.numero_documento},
                "finalidades": json.loads(row.finalidades_json),
                "canal": row.canal,
                "fechaRegistro": row.fecha_registro,
                "puedeContinuarCompra": row.puede_continuar_compra,
            }
        finally:
            if close_after:
                db.close()

    def buscar_pasajero_por_documento(self, numero_documento: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(PasajeroModel).filter_by(numero_documento=numero_documento).first()
            return self._pasajero_to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    def obtener_pasajero(self, id_pasajero: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(PasajeroModel).filter_by(id_pasajero=id_pasajero).first()
            return self._pasajero_to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    def guardar_pasajero(
        self,
        nombres: str,
        apellidos: str,
        tipo_documento: str,
        numero_documento: str,
        fecha_nacimiento: str,
        correo: str,
        telefono: str,
        id_consentimiento: str,
        tipo_pasajero: str,
        id_pasajero_fijo: str | None = None,
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            id_pas = id_pasajero_fijo or f"PAS-{secrets.randbelow(9000) + 1000}"
            if db.query(PasajeroModel).filter_by(id_pasajero=id_pas).first():
                id_pas = f"PAS-{secrets.randbelow(90000) + 10000}"
            nombre_completo = f"{nombres.strip()} {apellidos.strip()}"
            row = PasajeroModel(
                id_pasajero=id_pas,
                nombres=nombres.strip(),
                apellidos=apellidos.strip(),
                nombre_completo=nombre_completo,
                tipo_documento=tipo_documento.strip().upper(),
                numero_documento=numero_documento.strip(),
                fecha_nacimiento=fecha_nacimiento,
                correo=correo.strip(),
                telefono=telefono.strip(),
                id_consentimiento=id_consentimiento,
                tipo_pasajero=tipo_pasajero,
            )
            db.add(row)
            db.commit()
            return self._pasajero_to_dict(row)
        finally:
            if close_after:
                db.close()

    @staticmethod
    def _pasajero_to_dict(row: PasajeroModel) -> dict[str, Any]:
        return {
            "idPasajero": row.id_pasajero,
            "nombres": row.nombres,
            "apellidos": row.apellidos,
            "nombreCompleto": row.nombre_completo,
            "documento": {"tipo": row.tipo_documento, "numero": row.numero_documento},
            "fechaNacimiento": row.fecha_nacimiento,
            "correo": row.correo,
            "telefono": row.telefono,
            "idConsentimiento": row.id_consentimiento,
            "tipoPasajero": row.tipo_pasajero,
        }
