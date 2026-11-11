"""Modelos ORM para credenciales de API y tokens emitidos (MOD-05 · HU-001)."""
from sqlalchemy import Column, Integer, String, Text

from app.core.database import Base


class CredencialAPIModel(Base):
    __tablename__ = "credenciales_api"

    id_credencial = Column(String(40), primary_key=True, index=True)
    client_id = Column(String(80), unique=True, nullable=False, index=True)
    nombre_aplicacion = Column(String(120), nullable=False)
    responsable = Column(String(120), nullable=False)
    secret_hash = Column(String(128), nullable=False)
    alcance_json = Column(Text, nullable=False)
    estado = Column(String(20), nullable=False, default="activa")
    fecha_expiracion = Column(String(40), nullable=False)


class TokenEmitidoModel(Base):
    __tablename__ = "tokens_emitidos"

    jti = Column(String(40), primary_key=True, index=True)
    client_id = Column(String(80), nullable=False, index=True)
    alcance_json = Column(Text, nullable=False)
    expira_en = Column(Integer, nullable=False)
    exp_timestamp = Column(Integer, nullable=False)
