"""Modelos ORM para Estatus de Vuelo, Alertas, Check-in y Pases de Abordaje (MOD-04 y MOD-06 · HU-014 a HU-018)."""
from sqlalchemy import Column, Integer, String, Text

from app.core.database import Base


class EstatusVueloModel(Base):
    __tablename__ = "estatus_vuelos"

    id_vuelo = Column(String(20), primary_key=True, index=True)
    estado = Column(String(30), nullable=False, default="Programado")
    puerta = Column(String(15), nullable=False, default="B12")
    terminal = Column(String(15), nullable=False, default="1")
    hora_programada_salida = Column(String(35), nullable=False)
    hora_estimada_salida = Column(String(35), nullable=False)
    ultima_actualizacion = Column(String(35), nullable=False)


class HistorialEstatusVueloModel(Base):
    __tablename__ = "historial_estatus_vuelos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_evento = Column(String(30), unique=True, nullable=False, index=True)
    id_vuelo = Column(String(20), nullable=False, index=True)
    estado_anterior = Column(String(30), nullable=False)
    estado_nuevo = Column(String(30), nullable=False)
    puerta = Column(String(15), nullable=False)
    hora_estimada_salida = Column(String(35), nullable=False)
    fuente = Column(String(40), nullable=False, default="aerolinea")
    observacion = Column(String(200), nullable=True)
    actualizado_en = Column(String(35), nullable=False)


class AlertaPasajeroModel(Base):
    __tablename__ = "alertas_pasajeros"

    id_alerta = Column(String(30), primary_key=True, index=True)
    id_evento = Column(String(30), nullable=False, index=True)
    id_pasajero = Column(String(30), nullable=False, index=True)
    id_vuelo = Column(String(20), nullable=False, index=True)
    tipo_cambio = Column(String(30), nullable=False)
    mensaje = Column(Text, nullable=False)
    canal = Column(String(20), nullable=False, default="correo")
    estado_entrega = Column(String(40), nullable=False, default="entregado")
    fecha_envio = Column(String(35), nullable=False)


class CheckinModel(Base):
    __tablename__ = "checkins"

    id_checkin = Column(String(30), primary_key=True, index=True)
    codigo_pnr = Column(String(10), nullable=False, index=True)
    id_pasajero = Column(String(30), nullable=False, index=True)
    id_vuelo = Column(String(20), nullable=False, index=True)
    asiento = Column(String(10), nullable=False)
    estado_pasajero = Column(String(20), nullable=False, default="Check-in")
    id_pase_abordaje = Column(String(30), nullable=False)
    fecha_checkin = Column(String(35), nullable=False)


class PaseAbordajeModel(Base):
    __tablename__ = "pases_abordaje"

    id_pase_abordaje = Column(String(30), primary_key=True, index=True)
    codigo_pnr = Column(String(10), nullable=False, index=True)
    id_pasajero = Column(String(30), nullable=False, index=True)
    nombre_pasajero = Column(String(160), nullable=False)
    id_vuelo = Column(String(20), nullable=False, index=True)
    vuelo_json = Column(Text, nullable=False)
    asiento = Column(String(10), nullable=False)
    codigo_qr = Column(String(180), nullable=False)
    url_pdf = Column(String(180), nullable=False)
    enviado_a = Column(String(120), nullable=False)
    estado_envio = Column(String(40), nullable=False, default="entregado")
    version = Column(Integer, nullable=False, default=1)
