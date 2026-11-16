"""Suite completa de pruebas funcionales y unitarias para Semana 1 y Semana 2 del MVP de Sky Route."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.repositories.repositories.auth_repository import AuthRepository
from app.repositories.repositories.reserva_repository import ReservaRepository
from app.repositories.repositories.vuelo_repository import VueloRepository
from app.services.events.event_bus import event_bus
from app.services.services.reserva_service import ReservaService
from app.services.services.vuelo_service import VueloService
from main import app

TZ_COLOMBIA = timezone(timedelta(hours=-5))
client = TestClient(app)


def reset_db_and_get_token(alcance: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """Reinicia la base de datos SQLite y devuelve un token JWT válido con su encabezado Authorization."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    AuthRepository()
    VueloRepository()
    ReservaRepository()
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


# =====================================================================
# HU-001: Autenticar las aplicaciones que consumen los servicios (Casos 1 a 4)
# =====================================================================
def test_hu001_casos_1_a_4():
    reset_db_and_get_token()

    # Caso 1: credencial válida registrada con POST /api/v1/auth/credenciales
    reg = client.post(
        "/api/v1/auth/credenciales",
        json={
            "nombreAplicacion": "app-integradora",
            "responsable": "Andrés Mazo",
            "alcance": ["itinerarios:leer"],
        },
    )
    assert reg.status_code == 201
    secret = reg.json()["data"]["clientSecret"]

    tok_res = client.post(
        "/api/v1/auth/token",
        json={
            "clientId": "app-integradora",
            "clientSecret": secret,
            "alcance": ["itinerarios:leer"],
        },
    )
    assert tok_res.status_code == 200
    body1 = tok_res.json()
    assert body1["success"] is True
    assert body1["data"]["accessToken"]
    assert body1["data"]["tipo"] == "Bearer"

    # Caso 2: el token permite consumir otro servicio
    headers = {"Authorization": f"Bearer {body1['data']['accessToken']}"}
    itin_res = client.get(
        "/api/v1/itinerarios?origen=BOG&destino=MDE&fechaDesde=2026-11-20&fechaHasta=2026-11-20&cupos=1",
        headers=headers,
    )
    assert itin_res.status_code == 200

    # Caso 4: alcance no autorizado
    forbidden_res = client.post(
        "/api/v1/auth/token",
        json={
            "clientId": "app-integradora",
            "clientSecret": secret,
            "alcance": ["pagos:escribir"],
        },
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["mensaje"] == "El alcance solicitado no está autorizado para esta aplicación"

    # Caso 3: credencial revocada
    client.patch("/api/v1/auth/credenciales/app-integradora/revocar")
    rev_res = client.post(
        "/api/v1/auth/token",
        json={
            "clientId": "app-integradora",
            "clientSecret": secret,
            "alcance": ["itinerarios:leer"],
        },
    )
    assert rev_res.status_code == 401
    assert rev_res.json()["success"] is False
    assert rev_res.json()["mensaje"] == "La credencial no es válida o no está activa"


# =====================================================================
# HU-002: Buscar vuelos disponibles (Casos 1 a 4)
# =====================================================================
def test_hu002_casos_1_a_4(monkeypatch):
    _, headers = reset_db_and_get_token()

    # Caso 1: hay vuelos con cupos
    r1 = client.get(
        "/api/v1/itinerarios?origen=BOG&destino=MDE&fechaDesde=2026-11-20&fechaHasta=2026-11-20&cupos=2",
        headers=headers,
    )
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["success"] is True
    assert any(v["idVuelo"] == "VU-1023" and v["tarifa"]["valor"] == 289000 for v in b1["data"]["itinerarios"])

    # Caso 2: sin vuelos para la fecha
    r2 = client.get(
        "/api/v1/itinerarios?origen=BOG&destino=MDE&fechaDesde=2026-12-31&fechaHasta=2026-12-31&cupos=1",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["itinerarios"] == []
    assert r2.json()["mensaje"] == "No hay vuelos disponibles para los criterios indicados"

    # Caso 3: fecha en el pasado o con formato incorrecto
    r3 = client.get(
        "/api/v1/itinerarios?origen=BOG&destino=MDE&fechaDesde=20-11-2026&fechaHasta=2026-11-20&cupos=1",
        headers=headers,
    )
    assert r3.status_code == 400
    assert r3.json()["mensaje"] == "Formato de fecha no válido o fecha anterior a hoy. Debe ser YYYY-MM-DD"

    # Caso 4: base de datos no disponible
    from app.domain.exceptions.domain_exceptions import AppError

    def _fallo_db(*_args, **_kwargs):
        raise AppError("No fue posible consultar los itinerarios", status_code=503)

    monkeypatch.setattr(VueloRepository, "buscar_vuelos", _fallo_db)
    r4 = client.get(
        "/api/v1/itinerarios?origen=BOG&destino=MDE&fechaDesde=2026-11-20&fechaHasta=2026-11-20&cupos=1",
        headers=headers,
    )
    assert r4.status_code == 503
    assert r4.json()["mensaje"] == "No fue posible consultar los itinerarios"


# =====================================================================
# HU-003: Ver el mapa de asientos de un vuelo (Casos 1 a 4)
# =====================================================================
def test_hu003_casos_1_a_4():
    _, headers = reset_db_and_get_token()

    # Caso 1: vuelo con aeronave asignada (suma de asientos = 180)
    r1 = client.get("/api/v1/vuelos/VU-1023/asientos", headers=headers)
    assert r1.status_code == 200
    cabinas = r1.json()["data"]["cabinas"]
    total_asientos = sum(len(c["asientos"]) for c in cabinas)
    assert total_asientos == 180

    # Caso 2: asiento apartado por otro pasajero
    client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "14D", "idSesionCompra": "SES-1"},
        headers=headers,
    )
    r2 = client.get("/api/v1/vuelos/VU-1023/asientos", headers=headers)
    asientos_eco = [a for c in r2.json()["data"]["cabinas"] if c["clase"] == "Económica" for a in c["asientos"]]
    estado_14d = next(a["estado"] for a in asientos_eco if a["numero"] == "14D")
    assert estado_14d == "bloqueado"

    # Caso 3: vuelo inexistente
    r3 = client.get("/api/v1/vuelos/VU-9999/asientos", headers=headers)
    assert r3.status_code == 404
    assert r3.json()["mensaje"] == "El vuelo indicado no existe"

    # Caso 4: vuelo sin aeronave sincronizada
    r4 = client.get("/api/v1/vuelos/VU-2040/asientos", headers=headers)
    assert r4.status_code == 409
    assert r4.json()["mensaje"] == "El vuelo aún no tiene aeronave asignada"


# =====================================================================
# HU-004: Apartar un asiento mientras completo la compra (Casos 1 a 4 + concurrencia)
# =====================================================================
def test_hu004_casos_1_a_4_y_concurrencia():
    _, headers = reset_db_and_get_token()

    # Caso 1: asiento disponible
    r1 = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "14C", "idSesionCompra": "SES-88213"},
        headers=headers,
    )
    assert r1.status_code == 201
    assert r1.json()["data"]["estado"] == "bloqueado"

    # Caso 2: dos solicitudes simultáneas sobre un mismo asiento disponible (15A)
    def intentar_bloqueo(sesion: str) -> int:
        with TestClient(app) as local_client:
            resp = local_client.post(
                "/api/v1/asientos/bloqueos",
                json={"idVuelo": "VU-1023", "numeroAsiento": "15A", "idSesionCompra": sesion},
                headers=headers,
            )
            return resp.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codigos = sorted(list(pool.map(intentar_bloqueo, ["SES-A", "SES-B"])))
    assert codigos == [201, 409]

    # Caso 3: asiento ya bloqueado
    r3 = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "14C", "idSesionCompra": "SES-99999"},
        headers=headers,
    )
    assert r3.status_code == 409
    assert r3.json()["mensaje"] == "El asiento seleccionado ya no está disponible"

    # Caso 4: asiento inexistente
    r4 = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "99Z", "idSesionCompra": "SES-88213"},
        headers=headers,
    )
    assert r4.status_code == 404
    assert r4.json()["mensaje"] == "El asiento no existe en este vuelo"


# =====================================================================
# HU-005: Autorizar el tratamiento de mis datos personales (Casos 1 a 4)
# =====================================================================
def test_hu005_casos_1_a_4():
    _, headers = reset_db_and_get_token()

    # Caso 1: acepta la finalidad operativa
    r1 = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [
                {"finalidad": "operativa", "decision": "acepta"},
                {"finalidad": "comercial", "decision": "no acepta"},
            ],
            "canal": "web",
        },
        headers=headers,
    )
    assert r1.status_code == 201
    assert r1.json()["data"]["puedeContinuarCompra"] is True

    # Caso 2: rechaza la finalidad operativa
    r2 = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [{"finalidad": "operativa", "decision": "no acepta"}],
            "canal": "web",
        },
        headers=headers,
    )
    assert r2.status_code == 201
    assert r2.json()["data"]["puedeContinuarCompra"] is False

    # Caso 3: finalidad fuera del catálogo
    r3 = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [{"finalidad": "publicidad-terceros", "decision": "acepta"}],
            "canal": "web",
        },
        headers=headers,
    )
    assert r3.status_code == 422
    assert r3.json()["mensaje"] == "La finalidad 'publicidad-terceros' no está autorizada"

    # Caso 4: titular sin documento
    r4 = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC"},
            "finalidades": [{"finalidad": "operativa", "decision": "acepta"}],
            "canal": "web",
        },
        headers=headers,
    )
    assert r4.status_code == 400
    assert r4.json()["mensaje"] == "El documento del titular es obligatorio"


# =====================================================================
# HU-006: Registrar los datos de los pasajeros (Casos 1 a 4)
# =====================================================================
def test_hu006_casos_1_a_4():
    _, headers = reset_db_and_get_token()

    con_ok = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [{"finalidad": "operativa", "decision": "acepta"}],
            "canal": "web",
        },
        headers=headers,
    ).json()["data"]["idConsentimiento"]

    con_no = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "999999999"},
            "finalidades": [{"finalidad": "operativa", "decision": "no acepta"}],
            "canal": "web",
        },
        headers=headers,
    ).json()["data"]["idConsentimiento"]

    # Caso 1: adulto con consentimiento
    r1 = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Laura",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "CC",
            "numeroDocumento": "1098765432",
            "fechaNacimiento": "1995-04-12",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_ok,
        },
        headers=headers,
    )
    assert r1.status_code == 201
    assert r1.json()["data"]["tipoPasajero"] == "adulto"
    id_laura = r1.json()["data"]["idPasajero"]

    # Caso 2: menor de edad
    r2 = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Mateo",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "TI",
            "numeroDocumento": "1099887766",
            "fechaNacimiento": "2015-06-01",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_ok,
        },
        headers=headers,
    )
    assert r2.status_code == 201
    assert r2.json()["data"]["tipoPasajero"] == "menor"

    # Caso 3: sin consentimiento operativo
    r3 = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Pedro",
            "apellidos": "Pérez",
            "tipoDocumento": "CC",
            "numeroDocumento": "999999999",
            "fechaNacimiento": "1990-01-01",
            "correo": "pedro@correo.com",
            "telefono": "+57300000000",
            "idConsentimiento": con_no,
        },
        headers=headers,
    )
    assert r3.status_code == 422
    assert r3.json()["mensaje"] == "El titular no ha autorizado el tratamiento de datos para la compra"

    # Caso 4: documento ya registrado
    r4 = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Laura",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "CC",
            "numeroDocumento": "1098765432",
            "fechaNacimiento": "1995-04-12",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_ok,
        },
        headers=headers,
    )
    assert r4.status_code == 409
    assert r4.json()["mensaje"] == "El pasajero ya está registrado"
    assert r4.json()["data"]["idPasajero"] == id_laura


# =====================================================================
# HU-007: Crear la reserva y obtener el código PNR (Casos 1 a 4)
# =====================================================================
def test_hu007_casos_1_a_4():
    _, headers = reset_db_and_get_token()

    con_id = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [{"finalidad": "operativa", "decision": "acepta"}],
            "canal": "web",
        },
        headers=headers,
    ).json()["data"]["idConsentimiento"]

    pas_adulto = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Laura",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "CC",
            "numeroDocumento": "1098765432",
            "fechaNacimiento": "1995-04-12",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_id,
        },
        headers=headers,
    ).json()["data"]["idPasajero"]

    pas_menor = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Mateo",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "TI",
            "numeroDocumento": "1099887766",
            "fechaNacimiento": "2015-06-01",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_id,
        },
        headers=headers,
    ).json()["data"]["idPasajero"]

    blq_14c = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "14C", "idSesionCompra": "SES-1"},
        headers=headers,
    ).json()["data"]["idBloqueo"]

    # Caso 1: bloqueo vigente
    r1 = client.post(
        "/api/v1/reservas",
        json={"idVuelo": "VU-1023", "pasajeros": [{"idPasajero": pas_adulto, "idBloqueo": blq_14c}]},
        headers=headers,
    )
    assert r1.status_code == 201
    assert len(r1.json()["data"]["codigoPnr"]) == 6
    assert r1.json()["data"]["estado"] == "Pendiente de pago"

    # Caso 2: adulto y menor en la misma reserva
    blq_15a = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "15A", "idSesionCompra": "SES-2"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    blq_15b = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "15B", "idSesionCompra": "SES-2"},
        headers=headers,
    ).json()["data"]["idBloqueo"]

    r2 = client.post(
        "/api/v1/reservas",
        json={
            "idVuelo": "VU-1023",
            "pasajeros": [
                {"idPasajero": pas_adulto, "idBloqueo": blq_15a},
                {"idPasajero": pas_menor, "idBloqueo": blq_15b},
            ],
        },
        headers=headers,
    )
    assert r2.status_code == 201
    assert len(r2.json()["data"]["pasajeros"]) == 2
    assert r2.json()["data"]["total"]["valor"] == 289000 * 2

    # Caso 3: bloqueo vencido (hace 20 minutos)
    hace_20_min = datetime.now(TZ_COLOMBIA) - timedelta(minutes=20)
    blq_vencido = VueloService().bloquear_asiento(
        id_vuelo="VU-1023",
        numero_asiento="16C",
        id_sesion_compra="SES-OLD",
        ahora=hace_20_min,
        id_bloqueo_fijo="BLQ-55821",
    )["idBloqueo"]
    r3 = client.post(
        "/api/v1/reservas",
        json={"idVuelo": "VU-1023", "pasajeros": [{"idPasajero": pas_adulto, "idBloqueo": blq_vencido}]},
        headers=headers,
    )
    assert r3.status_code == 409
    assert r3.json()["mensaje"] == "El bloqueo del asiento 16C venció; selecciónelo de nuevo"

    # Caso 4: menor sin acompañante
    blq_17a = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "17A", "idSesionCompra": "SES-4"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    r4 = client.post(
        "/api/v1/reservas",
        json={"idVuelo": "VU-1023", "pasajeros": [{"idPasajero": pas_menor, "idBloqueo": blq_17a}]},
        headers=headers,
    )
    assert r4.status_code == 422
    assert r4.json()["mensaje"] == "Un menor de edad debe viajar con un adulto en la misma reserva"


# =====================================================================
# HU-008 y HU-009: Equipaje adicional y Pago con tarjeta (Casos 1 a 4)
# =====================================================================
def test_hu008_y_hu009_casos_1_a_4():
    _, headers = reset_db_and_get_token()

    con_id = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [{"finalidad": "operativa", "decision": "acepta"}],
            "canal": "web",
        },
        headers=headers,
    ).json()["data"]["idConsentimiento"]

    pas_id = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Laura",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "CC",
            "numeroDocumento": "1098765432",
            "fechaNacimiento": "1995-04-12",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_id,
        },
        headers=headers,
    ).json()["data"]["idPasajero"]

    blq_id = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "14C", "idSesionCompra": "SES-88213"},
        headers=headers,
    ).json()["data"]["idBloqueo"]

    reserva = ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas_id, "idBloqueo": blq_id}],
        codigo_pnr_fijo="K7Q2MZ",
    )
    pnr = reserva["codigoPnr"]

    # HU-008 Caso 1: maleta dentro del límite (23 kg bodega -> cargo 95000, total 384000)
    cat = client.get(f"/api/v1/reservas/{pnr}/servicios-suplementarios", headers=headers)
    assert cat.status_code == 200
    eq1 = client.post(
        f"/api/v1/reservas/{pnr}/equipajes",
        json={"idPasajero": pas_id, "tipo": "bodega", "pesoKg": 23, "piezas": 1},
        headers=headers,
    )
    assert eq1.status_code == 201
    assert eq1.json()["data"]["cargo"]["valor"] == 95000
    assert eq1.json()["data"]["totalReserva"]["valor"] == 384000

    # HU-008 Caso 3: peso excedido (32 kg > 23 kg)
    eq3 = client.post(
        f"/api/v1/reservas/{pnr}/equipajes",
        json={"idPasajero": pas_id, "tipo": "bodega", "pesoKg": 32, "piezas": 1},
        headers=headers,
    )
    assert eq3.status_code == 422
    assert eq3.json()["mensaje"] == "El peso por pieza supera el máximo permitido de 23 kg"

    # HU-009 Caso 4: monto distinto al saldo (289000 != 384000)
    cob4 = client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": pnr,
            "monto": 289000,
            "moneda": "COP",
            "tokenMedioPago": "tok_4f9a21c7",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "pago-K7Q2MZ-monto-mal"},
    )
    assert cob4.status_code == 422
    assert cob4.json()["mensaje"] == "El monto no coincide con el saldo pendiente de la reserva"

    # HU-009 Caso 3: pago rechazado por el simulador
    cob3 = client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": pnr,
            "monto": 384000,
            "moneda": "COP",
            "tokenMedioPago": "tok_rechazado_99",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "pago-K7Q2MZ-rechazado"},
    )
    assert cob3.status_code == 200
    assert cob3.json()["success"] is False
    assert cob3.json()["data"]["estado"] == "rechazada"

    # HU-009 Caso 1: pago aprobado
    cob1 = client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": pnr,
            "monto": 384000,
            "moneda": "COP",
            "tokenMedioPago": "tok_4f9a21c7",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "pago-K7Q2MZ-1"},
    )
    assert cob1.status_code == 201
    assert cob1.json()["data"]["estado"] == "aprobada"
    id_tx = cob1.json()["data"]["idTransaccion"]

    # Verificar que la reserva quedó Confirmada y sin saldo (HU-011)
    cons = client.get(f"/api/v1/reservas/{pnr}?apellido=Gomez", headers=headers)
    assert cons.status_code == 200
    assert cons.json()["data"]["estado"] == "Confirmada"
    assert cons.json()["data"]["saldoPendiente"]["valor"] == 0

    # HU-009 Caso 2: solicitud repetida con la misma Idempotency-Key
    cob2 = client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": pnr,
            "monto": 384000,
            "moneda": "COP",
            "tokenMedioPago": "tok_4f9a21c7",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "pago-K7Q2MZ-1"},
    )
    assert cob2.status_code == 200
    assert cob2.json()["data"]["idTransaccion"] == id_tx

    # HU-008 Caso 2: agregar maleta a reserva ya pagada genera nuevo saldoPendiente
    eq2 = client.post(
        f"/api/v1/reservas/{pnr}/equipajes",
        json={"idPasajero": pas_id, "tipo": "cabina", "pesoKg": 10, "piezas": 1},
        headers=headers,
    )
    assert eq2.status_code == 201
    assert eq2.json()["data"]["saldoPendiente"]["valor"] == 55000

    # HU-008 Caso 4: reserva cancelada no permite agregar equipaje
    ReservaRepository().actualizar_estado_reserva(pnr, "Cancelada")
    eq4 = client.post(
        f"/api/v1/reservas/{pnr}/equipajes",
        json={"idPasajero": pas_id, "tipo": "bodega", "pesoKg": 20, "piezas": 1},
        headers=headers,
    )
    assert eq4.status_code == 409
    assert eq4.json()["mensaje"] == "No se pueden agregar servicios a una reserva cancelada"


# =====================================================================
# HU-012 y HU-013: Liberación automática con reloj simulado y Cancelación/Reembolso
# =====================================================================
def test_hu012_y_hu013_casos_1_a_4():
    _, headers = reset_db_and_get_token()

    # HU-012 Caso 1: bloqueo vencido hace 16 minutos
    hace_16_min = datetime.now(TZ_COLOMBIA) - timedelta(minutes=16)
    VueloService().bloquear_asiento(
        id_vuelo="VU-1023",
        numero_asiento="15A",
        id_sesion_compra="SES-EXP",
        ahora=hace_16_min,
        id_bloqueo_fijo="BLQ-55819",
    )
    del_ok = client.delete("/api/v1/asientos/bloqueos/BLQ-55819?motivo=vencimiento", headers=headers)
    assert del_ok.status_code == 200
    assert del_ok.json()["data"]["estadoAsiento"] == "disponible"

    # HU-012 Caso 3: bloqueo todavía vigente (creado hace 5 minutos)
    hace_5_min = datetime.now(TZ_COLOMBIA) - timedelta(minutes=5)
    VueloService().bloquear_asiento(
        id_vuelo="VU-1023",
        numero_asiento="15B",
        id_sesion_compra="SES-VIG",
        ahora=hace_5_min,
        id_bloqueo_fijo="BLQ-55830",
    )
    del_vig = client.delete("/api/v1/asientos/bloqueos/BLQ-55830?motivo=vencimiento", headers=headers)
    assert del_vig.status_code == 409
    assert del_vig.json()["mensaje"] == "El bloqueo aún está vigente y no puede liberarse por vencimiento"

    # Preparar pasajero para HU-012 Casos 2/4 y HU-013 Casos 1 a 4
    con_id = client.post(
        "/api/v1/privacidad/consentimientos",
        json={
            "titular": {"tipoDocumento": "CC", "numeroDocumento": "1098765432"},
            "finalidades": [{"finalidad": "operativa", "decision": "acepta"}],
            "canal": "web",
        },
        headers=headers,
    ).json()["data"]["idConsentimiento"]

    pas_id = client.post(
        "/api/v1/pasajeros",
        json={
            "nombres": "Laura",
            "apellidos": "Gómez Ruiz",
            "tipoDocumento": "CC",
            "numeroDocumento": "1098765432",
            "fechaNacimiento": "1995-04-12",
            "correo": "laura.gomez@correo.com",
            "telefono": "+573001234567",
            "idConsentimiento": con_id,
        },
        headers=headers,
    ).json()["data"]["idPasajero"]

    # HU-012 Caso 2: reserva pendiente vencida
    blq_18a = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "18A", "idSesionCompra": "SES-EXP-RES"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas_id, "idBloqueo": blq_18a}],
        codigo_pnr_fijo="EXP001",
        vence_en_fijo=(datetime.now(TZ_COLOMBIA) - timedelta(minutes=10)).isoformat(timespec="seconds"),
    )

    # HU-012 Caso 4 y HU-013 Caso 1: reserva pagada (K7Q2MZ) por 384.000 COP
    blq_14c = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "14C", "idSesionCompra": "SES-K7"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas_id, "idBloqueo": blq_14c}],
        codigo_pnr_fijo="K7Q2MZ",
    )
    client.post(
        "/api/v1/reservas/K7Q2MZ/equipajes",
        json={"idPasajero": pas_id, "tipo": "bodega", "pesoKg": 23, "piezas": 1},
        headers=headers,
    )
    client.post(
        "/api/v1/cobros",
        json={
            "codigoPnr": "K7Q2MZ",
            "monto": 384000,
            "moneda": "COP",
            "tokenMedioPago": "tok_4f9a21c7",
            "concepto": "reserva",
        },
        headers={**headers, "Idempotency-Key": "pago-K7Q2MZ-ok"},
    )

    # Ejecutar disparador HU-012: cancela EXP001 pero NO modifica K7Q2MZ
    venc_res = client.post("/api/v1/reservas/vencimientos/ejecutar", headers=headers)
    assert venc_res.status_code == 200
    assert "EXP001" in venc_res.json()["data"]["reservasCanceladas"]
    assert client.get("/api/v1/reservas/K7Q2MZ?apellido=Gomez", headers=headers).json()["data"]["estado"] == "Confirmada"

    # HU-013 Caso 1: cancelar reserva pagada K7Q2MZ -> penalidad 60000, reembolso 324000, estado Cancelación en trámite
    canc1 = client.post(
        "/api/v1/reservas/K7Q2MZ/cancelaciones",
        json={"apellido": "Gomez", "motivo": "Cambio de planes"},
        headers=headers,
    )
    assert canc1.status_code == 202
    assert canc1.json()["data"]["montoReembolso"]["valor"] == 324000
    assert canc1.json()["data"]["estadoReembolso"] == "Pendiente de aprobación"
    id_rem = canc1.json()["data"]["idReembolso"]

    # Segundo aprobador aprueba el reembolso (RN-15) -> reserva pasa a Cancelada y asiento 14C disponible
    aprob = client.post(
        f"/api/v1/reembolsos/{id_rem}/aprobaciones",
        json={"aprobador": "tesorero.jefe", "decision": "aprobar", "observacion": "Aprobado RN-15"},
        headers=headers,
    )
    assert aprob.status_code == 200
    assert aprob.json()["data"]["estado"] == "ejecutado"
    assert client.get("/api/v1/reservas/K7Q2MZ?apellido=Gomez", headers=headers).json()["data"]["estado"] == "Cancelada"

    # HU-013 Caso 3: reserva ya cancelada
    canc3 = client.post(
        "/api/v1/reservas/K7Q2MZ/cancelaciones",
        json={"apellido": "Gomez", "motivo": "Otra vez"},
        headers=headers,
    )
    assert canc3.status_code == 409
    assert canc3.json()["mensaje"] == "La reserva ya está cancelada"

    # HU-013 Caso 2: reserva sin pagar se cancela de inmediato con HTTP 200 y montoReembolso = 0
    blq_19a = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-1023", "numeroAsiento": "19A", "idSesionCompra": "SES-NOPAY"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-1023",
        pasajeros_input=[{"idPasajero": pas_id, "idBloqueo": blq_19a}],
        codigo_pnr_fijo="NOPAY1",
    )
    canc2 = client.post(
        "/api/v1/reservas/NOPAY1/cancelaciones",
        json={"apellido": "Gomez", "motivo": "No viajaré"},
        headers=headers,
    )
    assert canc2.status_code == 200
    assert canc2.json()["data"]["estado"] == "Cancelada"
    assert canc2.json()["data"]["montoReembolso"]["valor"] == 0

    # HU-013 Caso 4: vuelo ya realizado (VU-0900 del 2026-10-01)
    blq_old = client.post(
        "/api/v1/asientos/bloqueos",
        json={"idVuelo": "VU-0900", "numeroAsiento": "14C", "idSesionCompra": "SES-PAST"},
        headers=headers,
    ).json()["data"]["idBloqueo"]
    ReservaService().crear_reserva(
        id_vuelo="VU-0900",
        pasajeros_input=[{"idPasajero": pas_id, "idBloqueo": blq_old}],
        codigo_pnr_fijo="PAST01",
    )
    canc4 = client.post(
        "/api/v1/reservas/PAST01/cancelaciones",
        json={"apellido": "Gomez", "motivo": "Vuelo pasado"},
        headers=headers,
    )
    assert canc4.status_code == 422
    assert canc4.json()["mensaje"] == "No se puede cancelar una reserva después de la salida del vuelo"
