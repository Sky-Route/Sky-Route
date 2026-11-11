"""Modelos ORM para Reservas, Equipajes, Transacciones y Reembolsos (MOD-02 y MOD-03 · HU-007 a HU-013)."""
from sqlalchemy import Column, Integer, String, Text

from app.core.database import Base


class ReservaModel(Base):
    __tablename__ = "reservas"

    codigo_pnr = Column(String(10), primary_key=True, index=True)
    id_vuelo = Column(String(20), nullable=False, index=True)
    estado = Column(String(40), nullable=False, default="Pendiente de pago")
    vence_en = Column(String(35), nullable=True)
    apellido_titular = Column(String(80), nullable=False, index=True)
    vuelo_json = Column(Text, nullable=False)
    pasajeros_json = Column(Text, nullable=False)
    servicios_json = Column(Text, nullable=False, default="[]")
    total_valor = Column(Integer, nullable=False)
    saldo_pendiente = Column(Integer, nullable=False)
    moneda = Column(String(10), nullable=False, default="COP")
    motivo_cancelacion = Column(String(120), nullable=True)


class CatalogoEquipajeModel(Base):
    __tablename__ = "catalogo_equipaje"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(30), unique=True, nullable=False)
    peso_maximo_kg = Column(Integer, nullable=False)
    precio_valor = Column(Integer, nullable=False)
    moneda = Column(String(10), nullable=False, default="COP")


class EquipajeReservaModel(Base):
    __tablename__ = "equipajes_reserva"

    id_equipaje = Column(String(30), primary_key=True, index=True)
    codigo_pnr = Column(String(10), nullable=False, index=True)
    id_pasajero = Column(String(30), nullable=False)
    tipo = Column(String(30), nullable=False)
    peso_kg = Column(Integer, nullable=False)
    piezas = Column(Integer, nullable=False, default=1)
    cargo_valor = Column(Integer, nullable=False)
    moneda = Column(String(10), nullable=False, default="COP")


class TransaccionPagoModel(Base):
    __tablename__ = "transacciones_pago"

    id_transaccion = Column(String(30), primary_key=True, index=True)
    idempotency_key = Column(String(100), unique=True, nullable=False, index=True)
    codigo_pnr = Column(String(10), nullable=False, index=True)
    estado = Column(String(30), nullable=False)
    codigo_autorizacion = Column(String(40), nullable=True)
    monto_valor = Column(Integer, nullable=False)
    moneda = Column(String(10), nullable=False, default="COP")
    token_medio_pago = Column(String(80), nullable=False)
    concepto = Column(String(40), nullable=False, default="reserva")
    fecha = Column(String(35), nullable=False)


class ReembolsoModel(Base):
    __tablename__ = "reembolsos"

    id_reembolso = Column(String(30), primary_key=True, index=True)
    id_transaccion_original = Column(String(30), nullable=False)
    codigo_pnr = Column(String(10), nullable=False, index=True)
    estado = Column(String(40), nullable=False, default="Pendiente de aprobación")
    penalidad_valor = Column(Integer, nullable=False, default=0)
    monto_reembolso = Column(Integer, nullable=False)
    moneda = Column(String(10), nullable=False, default="COP")
    motivo = Column(String(120), nullable=False)
    solicitado_por = Column(String(80), nullable=False, default="sistema-reservas")
    aprobado_por = Column(String(80), nullable=True)
    observacion_aprobacion = Column(String(200), nullable=True)
    fecha_solicitud = Column(String(35), nullable=False)
    fecha_ejecucion = Column(String(35), nullable=True)
