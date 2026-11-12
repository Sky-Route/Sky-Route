"""Repository Layer: Persistencia de consecutivos y facturas electrónicas con adaptador Alegra (MOD-03 · HU-010)."""
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.domain.entities.reserva import TZ_COLOMBIA
from app.repositories.adapters.alegra_adapter import AlegraSimulatorAdapter
from app.repositories.database.facturas_models import ConsecutivoFacturaModel, FacturaElectronicaModel


class FacturaRepository:
    def __init__(self, db: Session | None = None, alegra_adapter: AlegraSimulatorAdapter | None = None):
        Base.metadata.create_all(bind=engine)
        self._external_db = db
        self.alegra = alegra_adapter or AlegraSimulatorAdapter()
        self._ensure_seed()

    def _session(self) -> tuple[Session, bool]:
        if self._external_db is not None:
            return self._external_db, False
        return SessionLocal(), True

    def _ensure_seed(self) -> None:
        db, close_after = self._session()
        try:
            if db.query(ConsecutivoFacturaModel).filter_by(prefijo="SRF").first() is None:
                db.add(ConsecutivoFacturaModel(prefijo="SRF", ultimo_numero=122))
                db.commit()
        finally:
            if close_after:
                db.close()

    def emitir_y_guardar_factura(
        self,
        codigo_pnr: str,
        subtotal: int,
        impuestos: list[dict[str, Any]],
        total: int,
        moneda: str = "COP",
    ) -> dict[str, Any]:
        db, close_after = self._session()
        try:
            existente = db.query(FacturaElectronicaModel).filter_by(codigo_pnr=codigo_pnr.strip().upper()).first()
            if existente:
                return self._to_dict(existente)

            consecutivo = db.query(ConsecutivoFacturaModel).filter_by(prefijo="SRF").first()
            if not consecutivo:
                consecutivo = ConsecutivoFacturaModel(prefijo="SRF", ultimo_numero=122)
                db.add(consecutivo)
                db.flush()

            consecutivo.ultimo_numero += 1
            numero_factura = f"SRF-{consecutivo.ultimo_numero:06d}"

            alegra_res = self.alegra.emitir_y_timbrar_factura(
                numero_factura=numero_factura,
                codigo_pnr=codigo_pnr,
                subtotal=subtotal,
                impuestos=impuestos,
                total=total,
                moneda=moneda,
            )
            fecha_emision = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")

            row = FacturaElectronicaModel(
                numero_factura=numero_factura,
                codigo_pnr=codigo_pnr.strip().upper(),
                codigo_unico=alegra_res["codigoUnico"],
                fecha_emision=fecha_emision,
                subtotal=subtotal,
                impuestos_json=json.dumps(impuestos),
                total=total,
                moneda=moneda,
                estado_validacion=alegra_res["estadoValidacion"],
                url_pdf=alegra_res["urlPdf"],
                url_xml=alegra_res["urlXml"],
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)
        finally:
            if close_after:
                db.close()

    def obtener_factura_por_pnr(self, codigo_pnr: str) -> dict[str, Any] | None:
        db, close_after = self._session()
        try:
            row = db.query(FacturaElectronicaModel).filter_by(codigo_pnr=codigo_pnr.strip().upper()).first()
            return self._to_dict(row) if row else None
        finally:
            if close_after:
                db.close()

    @staticmethod
    def _to_dict(row: FacturaElectronicaModel) -> dict[str, Any]:
        return {
            "numeroFactura": row.numero_factura,
            "codigoPnr": row.codigo_pnr,
            "codigoUnico": row.codigo_unico,
            "fechaEmision": row.fecha_emision,
            "subtotal": row.subtotal,
            "impuestos": json.loads(row.impuestos_json),
            "total": row.total,
            "moneda": row.moneda,
            "estadoValidacion": row.estado_validacion,
            "urlPdf": row.url_pdf,
            "urlXml": row.url_xml,
        }
