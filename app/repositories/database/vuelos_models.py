"""Modelos ORM para Rutas, Vuelos, Tarifas, Asientos y Bloqueos (MOD-01 · HU-002, HU-003, HU-004, HU-012)."""
from sqlalchemy import Boolean, Column, Integer, String

from app.core.database import Base


class VueloModel(Base):
    __tablename__ = "vuelos"

    id_vuelo = Column(String(20), primary_key=True, index=True)
    aerolinea = Column(String(80), nullable=False)
    origen = Column(String(3), nullable=False, index=True)
    destino = Column(String(3), nullable=False, index=True)
    fecha_salida = Column(String(10), nullable=False, index=True)
    salida = Column(String(35), nullable=False)
    llegada = Column(String(35), nullable=False)
    escalas = Column(Integer, nullable=False, default=0)
    clase = Column(String(30), nullable=False, default="Económica")
    tarifa_valor = Column(Integer, nullable=False)
    tarifa_moneda = Column(String(10), nullable=False, default="COP")
    tarifa_vigente = Column(Boolean, nullable=False, default=True)
    cupos_disponibles = Column(Integer, nullable=False)
    publicado = Column(Boolean, nullable=False, default=True)
    aeronave_modelo = Column(String(40), nullable=True)
    aeronave_capacidad = Column(Integer, nullable=False, default=0)
    aeronave_sincronizada = Column(Boolean, nullable=False, default=True)


class AsientoVueloModel(Base):
    __tablename__ = "asientos_vuelo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_vuelo = Column(String(20), nullable=False, index=True)
    numero = Column(String(10), nullable=False, index=True)
    clase = Column(String(30), nullable=False)
    estado = Column(String(20), nullable=False, default="disponible")


class BloqueoAsientoModel(Base):
    __tablename__ = "bloqueos_asientos"

    id_bloqueo = Column(String(30), primary_key=True, index=True)
    id_vuelo = Column(String(20), nullable=False, index=True)
    numero_asiento = Column(String(10), nullable=False, index=True)
    id_sesion_compra = Column(String(60), nullable=False)
    estado = Column(String(20), nullable=False, default="bloqueado")
    creado_en = Column(String(35), nullable=False)
    expira_en = Column(String(35), nullable=False)
    codigo_pnr = Column(String(10), nullable=True)
