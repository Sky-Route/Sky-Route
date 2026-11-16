"""Modelos ORM para Consentimientos de Privacidad (MOD-07 · HU-005) y Pasajeros (MOD-02 · HU-006)."""
from sqlalchemy import Boolean, Column, Integer, String, Text

from app.core.database import Base


class ConsentimientoModel(Base):
    __tablename__ = "consentimientos_privacidad"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_consentimiento = Column(String(30), unique=True, nullable=False, index=True)
    tipo_documento = Column(String(10), nullable=False)
    numero_documento = Column(String(30), nullable=False, index=True)
    finalidades_json = Column(Text, nullable=False)
    canal = Column(String(30), nullable=False)
    fecha_registro = Column(String(35), nullable=False)
    puede_continuar_compra = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)


class PasajeroModel(Base):
    __tablename__ = "pasajeros"

    id_pasajero = Column(String(30), primary_key=True, index=True)
    nombres = Column(String(80), nullable=False)
    apellidos = Column(String(80), nullable=False)
    nombre_completo = Column(String(160), nullable=False)
    tipo_documento = Column(String(10), nullable=False)
    numero_documento = Column(String(30), unique=True, nullable=False, index=True)
    fecha_nacimiento = Column(String(15), nullable=False)
    correo = Column(String(120), nullable=False)
    telefono = Column(String(30), nullable=False)
    id_consentimiento = Column(String(30), nullable=False)
    tipo_pasajero = Column(String(20), nullable=False)
