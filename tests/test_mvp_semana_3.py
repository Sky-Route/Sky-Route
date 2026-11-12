"""Suite completa de pruebas funcionales y unitarias para la Semana 3 del MVP de Sky Route
(HU-010, HU-011, HU-014, HU-015, HU-016, HU-017 y HU-018)."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.domain.entities.operacion import verificar_firma_codigo_qr_hu018
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.adapters.alegra_adapter import AlegraSimulatorAdapter
from app.repositories.adapters.notificaciones_adapter import (
    SendGridSimulatorAdapter,
    TwilioSimulatorAdapter,
)
from app.repositories.repositories.auth_repository import AuthRepository
from app.repositories.repositories.cliente_repository import ClienteRepository
from app.repositories.repositories.factura_repository import FacturaRepository
from app.repositories.repositories.operacion_repository import OperacionRepository
from app.repositories.repositories.reserva_repository import ReservaRepository
from app.repositories.repositories.vuelo_repository import VueloRepository
from app.services.events.event_bus import event_bus
from app.services.services.cliente_service import ClienteService
from app.services.services.factura_service import FacturaService
from app.services.services.operacion_service import OperacionService
from app.services.services.reserva_service import ReservaService
from main import app

TZ_COLOMBIA = timezone(timedelta(hours=-5))
client = TestClient(app)


def reset_env_semana3(alcance: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """Reinicia las tablas SQLite, suscribe los listeners de eventos y emite un token JWT."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    AlegraSimulatorAdapter.entidad_fiscal_disponible = True
    SendGridSimulatorAdapter.disponible = True
    TwilioSimulatorAdapter.disponible = True
    OperacionService.RELOJ_ACTUAL = datetime(2026, 11, 19, 10, 0, 0, tzinfo=TZ_COLOMBIA)

    AuthRepository()
    VueloRepository()
    ReservaRepository()
    FacturaRepository()
    OperacionRepository()
    ReservaService()
    FacturaService()
    OperacionService()
    event_bus.clear_history()

    scopes = alcance or [
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
    res = client.post(
        "/api/v1/auth/token",
        json={
            "clientId": "frontend-web",
            "clientSecret": "skyroute-secret-2026",
            "alcance": scopes,
        },
    )
    assert res.status_code == 200
    token = res.json()["data"]["accessToken"]
    return token, {"Authorization": f"Bearer {token}"}


def crear_pasajero_y_reserva_base(
    headers: dict[str, str],
    codigo_pnr: str = "K7Q2MZ",
    asiento: str = "14C",
    pagar: bool = True,
    con_equipaje: bool = True,
) -> tuple[str, str]:
    """Crea consentimiento CON-7781, pasajero PAS-3102 (Laura Gómez Ruiz) y reserva K7Q2MZ."""
    con = ClienteService().registrar_consentimiento(
        titular={"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
        finalidades=[{"finalidad": "operativa", "decision": "acepta"}],
        canal="web",
        id_consentimiento_fijo="CON-7781",
    )
    pas = ClienteService().registrar_pasajero(
        nombres="Laura",
        apellidos="Gómez Ruiz",
        tipo_documento="CC",
        numero_documento="1098765432",
        fecha_nacimiento="1995-04-12",
        correo="laura.gomez@correo.com",
        telefono="+573001234567",
        id_consentimiento=con["idConsentimiento"],
        id_pasajero_fijo="PAS-3102",
    )
    blq = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": asiento, "idSesionCompra": f"SES-{codigo_pnr}"},
        headers=headers,
    ).json()["data"]["idBloqueo"]

    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas["idPasajero"], "idBloqueo": blq}],
        codigo_pnr_fijo=codigo_pnr,
    )
    monto = 289000
    if con_equipaje:
        client.post(
            f"/api/v1/reservas/{codigo_pnr}/equipajes",
            json={"idPasajero": pas["idPasajero"], "tipo": "bodega", "pesoKg": 23, "piezas": 1},
            headers=headers,
        )
        monto = 384000

    if pagar:
        client.post(
            "/api/v1/cobros",
            json={
                "codigoPnr": codigo_pnr,
                "monto": monto,
                "moneda": "COP",
                "tokenMedioPago": "tok_4f9a21c7",
                "concepto": "reserva",
            },
            headers={**headers, "Idempotency-Key": f"idem-{codigo_pnr}"},
        )
    return pas["idPasajero"], codigo_pnr


# =====================================================================
# HU-010: Obtener la factura electrónica de la compra (Casos 1 a 4)
# =====================================================================
def test_hu010_casos_1_a_4():
    _, headers = reset_env_semana3()
    id_pas, pnr = crear_pasajero_y_reserva_base(headers, codigo_pnr="K7Q2MZ", pagar=True, con_equipaje=True)

    # Caso 1: reserva pagada -> HTTP 200, total 384000, subtotal + impuestos == total, enlaces PDF y XML
    r1 = client.get(f"/api/v1/facturas/{pnr}?apellido=Gomez", headers=headers)
    assert r1.status_code == 200
    d1 = r1.json()["data"]
    assert d1["total"] == 384000
    assert d1["subtotal"] + sum(i["valor"] for i in d1["impuestos"]) == d1["total"]
    assert d1["estadoValidacion"] == "validada"
    assert d1["urlPdf"].endswith(".pdf")
    assert d1["urlXml"].endswith(".xml")

    # Caso 2: entidad fiscal sin respuesta -> estadoValidacion = "pendiente de validación"
    AlegraSimulatorAdapter.entidad_fiscal_disponible = False
    blq2 = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "15A", "idSesionCompra": "SES-F2"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": id_pas, "idBloqueo": blq2}],
        codigo_pnr_fijo="FAC002",
    )
    client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": "FAC002",
            "monto": 289000,
            "moneda": "COP",
            "tokenMedioPago": "tok_4f9a21c7",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "idem-FAC002"},
    )
    r2 = client.get("/api/v1/facturas/FAC002?apellido=Gomez", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["estadoValidacion"] == "pendiente de validación"
    AlegraSimulatorAdapter.entidad_fiscal_disponible = True

    # Caso 3: reserva sin pagar -> HTTP 404
    blq3 = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "16A", "idSesionCompra": "SES-F3"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": id_pas, "idBloqueo": blq3}],
        codigo_pnr_fijo="NOPAY9",
    )
    r3 = client.get("/api/v1/facturas/NOPAY9?apellido=Gomez", headers=headers)
    assert r3.status_code == 404
    assert r3.json()["mensaje"] == "La reserva aún no tiene factura: su pago no está completo"

    # Caso 4: apellido que no corresponde -> HTTP 404
    r4 = client.get(f"/api/v1/facturas/{pnr}?apellido=Perez", headers=headers)
    assert r4.status_code == 404
    assert r4.json()["mensaje"] == "No se encontró una factura para los datos indicados"


# =====================================================================
# HU-011: Consultar el estado de mi reserva (Casos 1 a 4)
# =====================================================================
def test_hu011_casos_1_a_4():
    _, headers = reset_env_semana3()
    id_pas, pnr = crear_pasajero_y_reserva_base(headers, codigo_pnr="K7Q2MZ", pagar=True)

    # Caso 1: reserva confirmada
    r1 = client.get(f"/api/v1/reservas/{pnr}?apellido=Gomez", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["data"]["estado"] == "Confirmada"
    assert r1.json()["data"]["saldoPendiente"]["valor"] == 0

    # Caso 2: reserva pendiente de pago
    blq2 = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "15B", "idSesionCompra": "SES-PND"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": id_pas, "idBloqueo": blq2}],
        codigo_pnr_fijo="PND001",
    )
    r2 = client.get("/api/v1/reservas/PND001?apellido=Gomez", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["estado"] == "Pendiente de pago"
    assert r2.json()["data"]["venceEn"] is not None

    # Caso 3: PNR con formato incorrecto
    r3 = client.get("/api/v1/reservas/K7Q?apellido=Gomez", headers=headers)
    assert r3.status_code == 400
    assert r3.json()["mensaje"] == "El código de reserva debe tener 6 caracteres alfanuméricos"

    # Caso 4: apellido que no corresponde
    r4 = client.get(f"/api/v1/reservas/{pnr}?apellido=Perez", headers=headers)
    assert r4.status_code == 404
    assert r4.json()["mensaje"] == "No se encontró una reserva con los datos indicados"


# =====================================================================
# HU-014, HU-015 y HU-016: Estatus operativo, Alertas y Consulta de vuelo
# =====================================================================
def test_hu014_hu015_hu016_casos_1_a_4(monkeypatch):
    _, headers = reset_env_semana3()
    id_pas, _ = crear_pasajero_y_reserva_base(headers, codigo_pnr="K7Q2MZ", pagar=True)

    # Pasajero con reserva cancelada (HU-015 Caso 3)
    pas_canc = ClienteService().registrar_pasajero(
        nombres="Carlos",
        apellidos="Ruiz",
        tipo_documento="CC",
        numero_documento="1088776655",
        fecha_nacimiento="1992-08-20",
        correo="carlos@correo.com",
        telefono="+573112223344",
        id_consentimiento="CON-7781",
        id_pasajero_fijo="PAS-3999",
    )["idPasajero"]
    blq_canc = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "18C", "idSesionCompra": "SES-CANC"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas_canc, "idBloqueo": blq_canc}],
        codigo_pnr_fijo="CNC001",
    )
    ReservaRepository().actualizar_estado_reserva("CNC001", "Cancelada")

    # HU-016 Caso 1: vuelo sin novedades -> estado Programado
    st1 = client.get("/api/v1/vuelos/VU-1023/estatus", headers=headers)
    assert st1.status_code == 200
    assert st1.json()["data"]["estado"] == "Programado"
    assert st1.json()["data"]["horaEstimadaSalida"] == st1.json()["data"]["horaProgramadaSalida"]

    # HU-014 Caso 1: retraso informado -> publica vuelo.estatus.cambiado
    up1 = client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={
            "estado": "Retrasado",
            "puerta": "B12",
            "horaEstimadaSalida": "2026-11-20T09:30:00-05:00",
            "fuente": "aerolinea",
            "observacion": "Llegada tardía de la aeronave",
        },
        headers=headers,
    )
    assert up1.status_code == 200
    assert up1.json()["data"]["estadoNuevo"] == "Retrasado"

    # HU-016 Caso 2: consultar estado de vuelo retrasado
    st2 = client.get("/api/v1/vuelos/VU-1023/estatus", headers=headers)
    assert st2.status_code == 200
    assert st2.json()["data"]["estado"] == "Retrasado"
    assert st2.json()["data"]["horaEstimadaSalida"] == "2026-11-20T09:30:00-05:00"

    # HU-015 Caso 1: pasajero con reserva confirmada recibe alerta entregada
    alr1 = client.get(f"/api/v1/alertas?idPasajero={id_pas}", headers=headers)
    assert alr1.status_code == 200
    alertas_pas = alr1.json()["data"]["alertas"]
    assert len(alertas_pas) == 1
    assert alertas_pas[0]["tipoCambio"] == "Retrasado"
    assert alertas_pas[0]["estadoEntrega"] == "entregado"

    # HU-015 Caso 2: reenviar exactamente el mismo evento no duplica la alerta
    ultimo_evento = next(
        e["payload"] for e in reversed(event_bus.published_events) if e["topico"] == "vuelo.estatus.cambiado"
    )
    event_bus.publish("vuelo.estatus.cambiado", ultimo_evento)
    alr2 = client.get(f"/api/v1/alertas?idPasajero={id_pas}", headers=headers)
    assert len(alr2.json()["data"]["alertas"]) == 1

    # HU-015 Caso 3: pasajero de reserva cancelada no recibe alerta
    alr_canc = client.get(f"/api/v1/alertas?idPasajero={pas_canc}", headers=headers)
    assert alr_canc.status_code == 200
    assert alr_canc.json()["data"]["alertas"] == []

    # HU-014 Caso 2 y HU-015 Caso 4: cambio de puerta en 'En sala' con ambos proveedores caídos
    client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={"estado": "En sala", "puerta": "B12"},
        headers=headers,
    )
    SendGridSimulatorAdapter.disponible = False
    TwilioSimulatorAdapter.disponible = False
    up2 = client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={"estado": "En sala", "puerta": "B15"},
        headers=headers,
    )
    assert up2.status_code == 200
    assert up2.json()["data"]["puerta"] == "B15"
    SendGridSimulatorAdapter.disponible = True
    TwilioSimulatorAdapter.disponible = True

    alr4 = client.get(f"/api/v1/alertas?idPasajero={id_pas}", headers=headers).json()["data"]["alertas"]
    assert alr4[-1]["estadoEntrega"] == "pendiente de reintento"

    # HU-014 Caso 3: transición inválida (de Cancelado a Embarcando)
    client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={"estado": "Cancelado", "puerta": "B15"},
        headers=headers,
    )
    up3 = client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={"estado": "Embarcando", "puerta": "B15"},
        headers=headers,
    )
    assert up3.status_code == 409
    assert up3.json()["mensaje"] == "No se puede pasar de 'Cancelado' a 'Embarcando'"

    # HU-014 Caso 4: usuario sin rol/alcance de operaciones
    tok_atencion = client.post(
        "/api/v1/auth/token",
        json={
            "clientId": "frontend-web",
            "clientSecret": "skyroute-secret-2026",
            "alcance": ["itinerarios:leer"],
        },
    ).json()["data"]["accessToken"]
    up4 = client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={"estado": "Retrasado"},
        headers={"Authorization": f"Bearer {tok_atencion}"},
    )
    assert up4.status_code == 403
    assert up4.json()["mensaje"] == "No tiene permiso para actualizar el estado del vuelo"

    # HU-016 Caso 3: vuelo inexistente
    st3 = client.get("/api/v1/vuelos/VU-9999/estatus", headers=headers)
    assert st3.status_code == 404
    assert st3.json()["mensaje"] == "El vuelo indicado no existe"

    # HU-016 Caso 4: base de datos no disponible
    def _fallo_db_estatus(*_args, **_kwargs):
        raise AppError("No fue posible consultar el estado del vuelo", status_code=503)

    monkeypatch.setattr(OperacionRepository, "obtener_o_inicializar_estatus_vuelo", _fallo_db_estatus)
    st4 = client.get("/api/v1/vuelos/VU-1023/estatus", headers=headers)
    assert st4.status_code == 503
    assert st4.json()["mensaje"] == "No fue posible consultar el estado del vuelo"


# =====================================================================
# HU-017 y HU-018: Hacer check-in en línea y Obtener tarjeta de embarque
# =====================================================================
def test_hu017_y_hu018_casos_1_a_4():
    _, headers = reset_env_semana3()
    id_pas, pnr = crear_pasajero_y_reserva_base(headers, codigo_pnr="K7Q2MZ", pagar=True)

    # HU-017 Caso 2: consulta de la ventana el 2026-11-18 -> "en espera de apertura"
    OperacionService.RELOJ_ACTUAL = datetime(2026, 11, 18, 12, 0, 0, tzinfo=TZ_COLOMBIA)
    ven = client.get("/api/v1/vuelos/VU-1023/ventana-checkin", headers=headers)
    assert ven.status_code == 200
    assert ven.json()["data"]["estadoVentana"] == "en espera de apertura"
    assert ven.json()["data"]["aperturaVentana"] == "2026-11-19T08:15:00-05:00"

    # HU-017 Caso 3: intentar check-in fuera de la ventana (2026-11-18) -> HTTP 422
    chk_fuera = client.post(
        "/api/v1/checkin",
        json={"codigoPnr": pnr, "idPasajero": id_pas, "idVuelo": "VU-1023"},
        headers=headers,
    )
    assert chk_fuera.status_code == 422
    assert chk_fuera.json()["mensaje"] == "El check-in en línea está disponible entre 24 y 2 horas antes de la salida"

    # HU-018 Caso 3: consultar pase antes de hacer check-in -> HTTP 409
    pab_antes = client.get(f"/api/v1/pases-abordaje?codigoPnr={pnr}&idPasajero={id_pas}", headers=headers)
    assert pab_antes.status_code == 409
    assert pab_antes.json()["mensaje"] == "El pase de abordaje se genera después del check-in"

    # HU-017 Caso 4: reserva sin pagar dentro de la ventana -> HTTP 422
    OperacionService.RELOJ_ACTUAL = datetime(2026, 11, 19, 10, 0, 0, tzinfo=TZ_COLOMBIA)
    blq_impaga = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "19B", "idSesionCompra": "SES-IMP"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": id_pas, "idBloqueo": blq_impaga}],
        codigo_pnr_fijo="IMP001",
    )
    chk_impaga = client.post(
        "/api/v1/checkin",
        json={"codigoPnr": "IMP001", "idPasajero": id_pas, "idVuelo": "VU-1023"},
        headers=headers,
    )
    assert chk_impaga.status_code == 422
    assert chk_impaga.json()["mensaje"] == "La reserva debe estar pagada para hacer check-in"

    # HU-017 Caso 1: check-in dentro de la ventana (2026-11-19 10:00) -> HTTP 201
    chk_ok = client.post(
        "/api/v1/checkin",
        json={"codigoPnr": pnr, "idPasajero": id_pas, "idVuelo": "VU-1023"},
        headers=headers,
    )
    assert chk_ok.status_code == 201
    assert chk_ok.json()["data"]["estadoPasajero"] == "Check-in"
    assert chk_ok.json()["data"]["idPaseAbordaje"]

    # HU-018 Caso 1 y Caso 2: obtener pase de abordaje con QR firmado y enviado por correo
    pab_ok = client.get(f"/api/v1/pases-abordaje?codigoPnr={pnr}&idPasajero={id_pas}", headers=headers)
    assert pab_ok.status_code == 200
    d_pab = pab_ok.json()["data"]
    assert d_pab["asiento"] == "14C"
    assert verificar_firma_codigo_qr_hu018(d_pab["codigoQR"]) is True
    assert d_pab["enviadoA"] == "laura.gomez@correo.com"
    assert d_pab["estadoEnvio"] == "entregado"

    # HU-018 Caso 4: pasajero que no pertenece a la reserva -> HTTP 404
    pab_404 = client.get(f"/api/v1/pases-abordaje?codigoPnr={pnr}&idPasajero=PAS-9001", headers=headers)
    assert pab_404.status_code == 404
    assert pab_404.json()["mensaje"] == "No se encontró un pase para los datos indicados"


# =====================================================================
# Casos adicionales de corrección HU-010 y HU-015 (Puntos 1, 2 y 3)
# =====================================================================
def test_punto1_hu010_alegra_caido_y_reintento_exitoso():
    """(1) Alegra caído al pagar deja la factura en 'pendiente de validación' y luego el reintento la pasa a 'validada'."""
    _, headers = reset_env_semana3()
    AlegraSimulatorAdapter.entidad_fiscal_disponible = False
    _, pnr = crear_pasajero_y_reserva_base(headers, codigo_pnr="RTR001", pagar=True, con_equipaje=False)

    r_pend = client.get(f"/api/v1/facturas/{pnr}?apellido=Gomez", headers=headers)
    assert r_pend.status_code == 200
    assert r_pend.json()["data"]["estadoValidacion"] == "pendiente de validación"

    # Alegra vuelve a estar disponible y se ejecuta POST /api/v1/facturas/reintentos
    AlegraSimulatorAdapter.entidad_fiscal_disponible = True
    r_retry = client.post("/api/v1/facturas/reintentos", headers=headers)
    assert r_retry.status_code == 200
    datos_retry = r_retry.json()["data"]
    assert datos_retry["procesadas"] == 1
    assert datos_retry["validadas"] == 1
    assert datos_retry["pendientes"] == 0

    r_val = client.get(f"/api/v1/facturas/{pnr}?apellido=Gomez", headers=headers)
    assert r_val.status_code == 200
    assert r_val.json()["data"]["estadoValidacion"] == "validada"


def test_punto2_hu015_sendgrid_caido_y_respaldo_sms_exitoso():
    """(2) Si SendGrid falla y Twilio está disponible, la alerta se entrega por respaldo SMS."""
    _, headers = reset_env_semana3()
    id_pas, _ = crear_pasajero_y_reserva_base(headers, codigo_pnr="SMS001", pagar=True, con_equipaje=False)

    SendGridSimulatorAdapter.disponible = False
    TwilioSimulatorAdapter.disponible = True

    up = client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={
            "estado": "Retrasado",
            "puerta": "B14",
            "horaEstimadaSalida": "2026-11-20T09:45:00-05:00",
        },
        headers=headers,
    )
    assert up.status_code == 200

    res_alr = client.get(f"/api/v1/alertas?idPasajero={id_pas}", headers=headers)
    assert res_alr.status_code == 200
    alertas = res_alr.json()["data"]["alertas"]
    assert len(alertas) == 1
    assert alertas[0]["canal"] == "sms"
    assert alertas[0]["estadoEntrega"] == "entregado"


def test_punto3_hu015_pasajero_sin_contacto_real_queda_sin_destino():
    """(3) Si el pasajero no tiene correo ni teléfono reales, no se envía nada y la alerta queda en 'sin destino'."""
    _, headers = reset_env_semana3()
    # Guardamos un pasajero sin correo ni teléfono reales en la tabla pasajeros
    pas_sin_contacto = ClienteRepository().guardar_pasajero(
        nombres="Andrés",
        apellidos="Sin Contacto",
        tipo_documento="CC",
        numero_documento="1099001122",
        fecha_nacimiento="1990-01-15",
        correo="",
        telefono="",
        id_consentimiento="CON-7781",
        tipo_pasajero="adulto",
        id_pasajero_fijo="PAS-SINDEST",
    )
    blq = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "20A", "idSesionCompra": "SES-SINDEST"},
        headers=headers,
    ).json()["data"]["idBloqueo"]

    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas_sin_contacto["idPasajero"], "idBloqueo": blq}],
        codigo_pnr_fijo="SND001",
    )
    client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": "SND001",
            "monto": 289000,
            "moneda": "COP",
            "tokenMedioPago": "tok_4f9a21c7",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "idem-SND001"},
    )

    up = client.patch(
        "/api/v1/vuelos/VU-1023/estatus",
        json={
            "estado": "Retrasado",
            "puerta": "B18",
            "horaEstimadaSalida": "2026-11-20T10:00:00-05:00",
        },
        headers=headers,
    )
    assert up.status_code == 200

    res_alr = client.get(f"/api/v1/alertas?idPasajero={pas_sin_contacto['idPasajero']}", headers=headers)
    assert res_alr.status_code == 200
    alertas = res_alr.json()["data"]["alertas"]
    assert len(alertas) == 1
    assert alertas[0]["estadoEntrega"] == "sin destino"
