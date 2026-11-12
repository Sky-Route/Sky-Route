"""Modelos ORM para Facturas Electrónicas y Consecutivos Fiscales (MOD-03 · HU-010)."""
from sqlalchemy import Column, Integer, String, Text

from app.core.database import Base


class ConsecutivoFacturaModel(Base):
    __tablename__ = "consecutivos_facturas"

    prefijo = Column(String(10), primary_key=True)
    ultimo_numero = Column(Integer, nullable=False, default=122)


class FacturaElectronicaModel(Base):
    __tablename__ = "facturas_electronicas"

    numero_factura = Column(String(20), primary_key=True, index=True)
    codigo_pnr = Column(String(10), unique=True, nullable=False, index=True)
    codigo_unico = Column(String(64), nullable=False)
    fecha_emision = Column(String(35), nullable=False)
    subtotal = Column(Integer, nullable=False)
    impuestos_json = Column(Text, nullable=False)
    total = Column(Integer, nullable=False)
    moneda = Column(String(10), nullable=False, default="COP")
    estado_validacion = Column(String(40), nullable=False, default="validada")
    url_pdf = Column(String(160), nullable=False)
    url_xml = Column(String(160), nullable=False)
