"""Repository Layer: Persistencia de credenciales de API y tokens emitidos (MOD-05 · HU-001)."""
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_client_secret
from app.domain.entities.auth import CredencialDeAPI
from app.repositories.database.auth_models import CredencialAPIModel, TokenEmitidoModel


class AuthRepository:
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
            existing = db.query(CredencialAPIModel).filter_by(client_id="frontend-web").first()
            if not existing:
                default_scopes = [
                    "itinerarios:leer",
                    "asientos:leer",
                    "asientos:escribir",
                    "privacidad:escribir",
                    "pasajeros:escribir",
                    "reservas:leer",
                    "reservas:escribir",
                    "pagos:escribir",
                    "facturas:leer",
                    "vuelos:escribir",
                    "vuelos:leer",
                    "alertas:leer",
                    "checkin:escribir",
                    "pases:leer",
                ]
                db.add(
                    CredencialAPIModel(
                        id_credencial="CRD-1001",
                        client_id="frontend-web",
                        nombre_aplicacion="frontend-web",
                        responsable="Integrador Frontend Sky Route",
                        secret_hash=hash_client_secret("skyroute-secret-2026"),
                        alcance_json=json.dumps(default_scopes),
                        estado="activa",
                        fecha_expiracion="2027-11-10T23:59:59-05:00",
                    )
                )
                db.commit()
        finally:
            if close_after:
                db.close()

    def guardar_credencial(
        self,
        nombre_aplicacion: str,
        responsable: str,
        alcance: list[str],
        secret_hash: str,
        client_id: str | None = None,
        estado: str = "activa",
        fecha_expiracion: str | None = None,
    ) -> CredencialDeAPI:
        db, close_after = self._session()
        try:
            cid = client_id or nombre_aplicacion.strip().lower().replace(" ", "-")
            exp = fecha_expiracion or (
                datetime.now(timezone(timedelta(hours=-5))) + timedelta(days=365)
            ).isoformat(timespec="seconds")
            model = db.query(CredencialAPIModel).filter_by(client_id=cid).first()
            if model:
                model.nombre_aplicacion = nombre_aplicacion
                model.responsable = responsable
                model.secret_hash = secret_hash
                model.alcance_json = json.dumps(alcance)
                model.estado = estado
                model.fecha_expiracion = exp
            else:
                id_cred = f"CRD-{secrets.randbelow(9000) + 1000}"
                model = CredencialAPIModel(
                    id_credencial=id_cred,
                    client_id=cid,
                    nombre_aplicacion=nombre_aplicacion,
                    responsable=responsable,
                    secret_hash=secret_hash,
                    alcance_json=json.dumps(alcance),
                    estado=estado,
                    fecha_expiracion=exp,
                )
                db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_entity(model)
        finally:
            if close_after:
                db.close()

    def obtener_por_client_id(self, client_id: str) -> CredencialDeAPI | None:
        db, close_after = self._session()
        try:
            model = db.query(CredencialAPIModel).filter_by(client_id=client_id).first()
            return self._to_entity(model) if model else None
        finally:
            if close_after:
                db.close()

    def cambiar_estado_credencial(self, client_id: str, nuevo_estado: str) -> CredencialDeAPI | None:
        db, close_after = self._session()
        try:
            model = db.query(CredencialAPIModel).filter_by(client_id=client_id).first()
            if not model:
                return None
            model.estado = nuevo_estado
            db.commit()
            db.refresh(model)
            return self._to_entity(model)
        finally:
            if close_after:
                db.close()

    def guardar_token_emitido(self, jti: str, client_id: str, alcance: list[str], expira_en: int, exp_ts: int) -> None:
        db, close_after = self._session()
        try:
            db.add(
                TokenEmitidoModel(
                    jti=jti,
                    client_id=client_id,
                    alcance_json=json.dumps(alcance),
                    expira_en=expira_en,
                    exp_timestamp=exp_ts,
                )
            )
            db.commit()
        finally:
            if close_after:
                db.close()

    @staticmethod
    def _to_entity(model: CredencialAPIModel) -> CredencialDeAPI:
        return CredencialDeAPI(
            id_credencial=model.id_credencial,
            client_id=model.client_id,
            nombre_aplicacion=model.nombre_aplicacion,
            responsable=model.responsable,
            secret_hash=model.secret_hash,
            alcance=json.loads(model.alcance_json),
            estado=model.estado,
            fecha_expiracion=model.fecha_expiracion,
        )
