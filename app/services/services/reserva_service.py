"""Service Layer: Creación de reservas PNR, equipajes, cobros, vencimientos y cancelaciones (HU-007 a HU-013)."""
from datetime import datetime, timedelta
from typing import Any

from app.domain.entities.reserva import (
    TZ_COLOMBIA,
    evaluar_cancelacion_y_penalidad_rn07_rn10,
    generar_codigo_pnr_unico,
    reserva_pendiente_esta_vencida_rn10,
    validar_cobro_reserva_rn10_rn12,
    validar_consulta_reserva_pnr,
    validar_reglas_creacion_reserva_rn06,
    validar_segundo_aprobador_reembolso_rn15,
    validar_y_calcular_equipaje_rn10,
)
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.repositories.cliente_repository import ClienteRepository
from app.repositories.repositories.reserva_repository import ReservaRepository
from app.repositories.repositories.vuelo_repository import VueloRepository
from app.services.events.event_bus import event_bus


class ReservaService:
    def __init__(
        self,
        reserva_repo: ReservaRepository | None = None,
        vuelo_repo: VueloRepository | None = None,
        cliente_repo: ClienteRepository | None = None,
    ):
        self.reserva_repo = reserva_repo or ReservaRepository()
        self.vuelo_repo = vuelo_repo or VueloRepository()
        self.cliente_repo = cliente_repo or ClienteRepository()
        event_bus.subscribe("pago.resultado", self._on_pago_resultado)

    def crear_reserva(
        self,
        id_vuelo: str,
        pasajeros_input: list[dict[str, str]],
        ahora: datetime | None = None,
        codigo_pnr_fijo: str | None = None,
        vence_en_fijo: str | None = None,
    ) -> dict[str, Any]:
        vuelo = self.vuelo_repo.obtener_vuelo(id_vuelo)
        if not vuelo:
            raise AppError("El vuelo indicado no existe", status_code=404)

        pasajeros_ficha: list[dict[str, Any]] = []
        for item in pasajeros_input:
            id_pas = item.get("idPasajero", "")
            id_blq = item.get("idBloqueo", "")
            ficha = self.cliente_repo.obtener_pasajero(id_pas)
            if not ficha:
                raise AppError(f"El pasajero '{id_pas}' no existe", status_code=404)
            pasajeros_ficha.append({**ficha, "idBloqueo": id_blq})

        # RN-06: validar que ningún menor viaje sin adulto en el mismo PNR antes de confirmar asientos
        validar_reglas_creacion_reserva_rn06(pasajeros_ficha)

        pnr = codigo_pnr_fijo or generar_codigo_pnr_unico(self.reserva_repo.codigos_pnr_existentes())
        confirmados: list[str] = []
        pasajeros_reserva: list[dict[str, Any]] = []

        try:
            for pf in pasajeros_ficha:
                conf = self.vuelo_repo.confirmar_bloqueo(
                    id_bloqueo=pf["idBloqueo"],
                    codigo_pnr=pnr,
                    ahora=ahora,
                )
                confirmados.append(pf["idBloqueo"])
                pasajeros_reserva.append(
                    {
                        "idPasajero": pf["idPasajero"],
                        "nombre": pf["nombreCompleto"],
                        "asiento": conf["numeroAsiento"],
                        "idBloqueo": pf["idBloqueo"],
                    }
                )
        except Exception:
            for id_blq_conf in confirmados:
                self.vuelo_repo.liberar_bloqueo(id_blq_conf, motivo="compensacion", ahora=ahora, forzar=True)
            raise

        now = ahora or datetime.now(TZ_COLOMBIA)
        if now.tzinfo is None:
            now = now.replace(tzinfo=TZ_COLOMBIA)
        vence_en = vence_en_fijo or (now + timedelta(hours=24)).isoformat(timespec="seconds")

        total_valor = int(vuelo["tarifa_valor"]) * len(pasajeros_reserva)
        moneda = vuelo["tarifa_moneda"]
        vuelo_resumen = {
            "idVuelo": vuelo["idVuelo"],
            "origen": vuelo["origen"],
            "destino": vuelo["destino"],
            "salida": vuelo["salida"],
        }
        apellido_titular = pasajeros_ficha[0]["apellidos"]

        creada = self.reserva_repo.guardar_reserva(
            codigo_pnr=pnr,
            id_vuelo=id_vuelo,
            estado="Pendiente de pago",
            vence_en=vence_en,
            apellido_titular=apellido_titular,
            vuelo=vuelo_resumen,
            pasajeros=pasajeros_reserva,
            total_valor=total_valor,
            saldo_pendiente=total_valor,
            moneda=moneda,
        )
        return {
            "codigoPnr": creada["codigoPnr"],
            "estado": creada["estado"],
            "venceEn": creada["venceEn"],
            "vuelo": creada["vuelo"],
            "pasajeros": [
                {"idPasajero": p["idPasajero"], "nombre": p["nombre"], "asiento": p["asiento"]}
                for p in creada["pasajeros"]
            ],
            "total": creada["total"],
        }

    def consultar_reserva(self, codigo_pnr: str, apellido: str | None = None) -> dict[str, Any]:
        pnr = (codigo_pnr or "").strip().upper()
        if len(pnr) != 6 or not pnr.isalnum():
            raise AppError("El código de reserva debe tener 6 caracteres alfanuméricos", status_code=400)
        reserva = self.reserva_repo.obtener_reserva(pnr)
        validar_consulta_reserva_pnr(pnr, apellido, reserva)
        return {
            "codigoPnr": reserva["codigoPnr"],
            "estado": reserva["estado"],
            "venceEn": reserva["venceEn"],
            "vuelo": reserva["vuelo"],
            "pasajeros": [
                {"idPasajero": p["idPasajero"], "nombre": p["nombre"], "asiento": p["asiento"]}
                for p in reserva["pasajeros"]
            ],
            "servicios": [{"tipo": s["tipo"], "pesoKg": s["pesoKg"]} for s in reserva["servicios"]],
            "total": reserva["total"],
            "saldoPendiente": reserva["saldoPendiente"],
        }

    def listar_opciones_equipaje(self, codigo_pnr: str) -> dict[str, Any]:
        reserva = self.reserva_repo.obtener_reserva(codigo_pnr)
        if not reserva:
            raise AppError("La reserva indicada no existe", status_code=404)
        return {
            "codigoPnr": reserva["codigoPnr"],
            "servicios": self.reserva_repo.listar_catalogo_equipaje(),
        }

    def agregar_equipaje(
        self,
        codigo_pnr: str,
        id_pasajero: str,
        tipo: str,
        peso_kg: int,
        piezas: int = 1,
    ) -> dict[str, Any]:
        reserva = self.reserva_repo.obtener_reserva(codigo_pnr)
        opcion = self.reserva_repo.obtener_opcion_equipaje(tipo)
        cargo, nuevo_total, nuevo_saldo = validar_y_calcular_equipaje_rn10(
            reserva=reserva,
            id_pasajero=id_pasajero,
            opcion_catalogo=opcion,
            peso_kg=peso_kg,
            piezas=piezas,
        )
        return self.reserva_repo.agregar_equipaje_reserva(
            codigo_pnr=reserva["codigoPnr"],
            id_pasajero=id_pasajero,
            tipo=tipo.strip().lower(),
            peso_kg=peso_kg,
            piezas=piezas,
            cargo_valor=cargo,
            nuevo_total=nuevo_total,
            nuevo_saldo=nuevo_saldo,
            moneda=reserva["total"]["moneda"],
        )

    def procesar_cobro(
        self,
        codigo_pnr: str,
        monto: int,
        moneda: str,
        token_medio_pago: str,
        concepto: str,
        idempotency_key: str | None,
    ) -> tuple[int, str, bool, dict[str, Any]]:
        if not (idempotency_key or "").strip():
            raise AppError("El encabezado Idempotency-Key es obligatorio", status_code=400)

        idem = idempotency_key.strip()
        previa = self.reserva_repo.obtener_transaccion_por_idempotencia(idem)
        if previa:
            # Caso 2 HU-009: solicitud repetida devuelve HTTP 200 con la misma idTransaccion sin segundo cobro
            es_exito = previa["estado"] == "aprobada"
            mensaje = "Pago aprobado" if es_exito else "El pago fue rechazado por la entidad bancaria"
            return 200, mensaje, es_exito, previa

        reserva = self.reserva_repo.obtener_reserva(codigo_pnr)
        validar_cobro_reserva_rn10_rn12(reserva=reserva, monto=monto)

        tx = self.reserva_repo.procesar_y_guardar_transaccion(
            idempotency_key=idem,
            codigo_pnr=reserva["codigoPnr"],
            monto=monto,
            moneda=moneda,
            token_medio_pago=token_medio_pago,
            concepto=concepto,
        )

        event_bus.publish(
            "pago.resultado",
            {
                "idTransaccion": tx["idTransaccion"],
                "codigoPnr": tx["codigoPnr"],
                "tipo": "cobro",
                "estado": tx["estado"],
                "monto": tx["monto"],
                "fecha": tx["fecha"],
            },
        )

        if tx["estado"] == "pendiente":
            return 202, "El pago quedó pendiente de confirmación bancaria", True, tx

        if tx["estado"] == "rechazada":
            return (
                200,
                "El pago fue rechazado por la entidad bancaria",
                False,
                {"idTransaccion": tx["idTransaccion"], "estado": "rechazada"},
            )

        return 201, "Pago aprobado", True, tx

    def _on_pago_resultado(self, evento: dict[str, Any]) -> None:
        codigo_pnr = evento.get("codigoPnr", "")
        tipo = evento.get("tipo")
        estado = evento.get("estado")
        reserva = self.reserva_repo.obtener_reserva(codigo_pnr)
        if not reserva:
            return

        if tipo == "cobro" and estado == "aprobada":
            self.reserva_repo.actualizar_estado_reserva(
                codigo_pnr=codigo_pnr,
                nuevo_estado="Confirmada",
                saldo_pendiente=0,
                vence_en=None,
            )
            event_bus.publish(
                "reserva.confirmada",
                {
                    "codigoPnr": codigo_pnr,
                    "estadoNuevo": "Confirmada",
                    "motivo": "pago_aprobado",
                    "pasajeros": reserva["pasajeros"],
                    "fecha": evento.get("fecha"),
                },
            )
        elif tipo == "reembolso" and estado == "ejecutado":
            self.reserva_repo.actualizar_estado_reserva(
                codigo_pnr=codigo_pnr,
                nuevo_estado="Cancelada",
                saldo_pendiente=0,
                vence_en=None,
            )
            for pas in reserva.get("pasajeros", []):
                id_blq = pas.get("idBloqueo")
                if id_blq:
                    try:
                        self.vuelo_repo.liberar_bloqueo(id_blq, motivo="cancelacion", forzar=True)
                    except Exception:
                        pass
            event_bus.publish(
                "reserva.cancelada",
                {
                    "codigoPnr": codigo_pnr,
                    "estadoNuevo": "Cancelada",
                    "motivo": "reembolso_ejecutado",
                    "pasajeros": reserva["pasajeros"],
                    "fecha": evento.get("fecha"),
                },
            )

    def ejecutar_liberacion_automatica(self, ahora: datetime | None = None) -> dict[str, Any]:
        """HU-012: Tarea programada que libera bloqueos vencidos en MOD-01 y cancela reservas impagas vencidas en MOD-02."""
        now = ahora or datetime.now(TZ_COLOMBIA)
        if now.tzinfo is None:
            now = now.replace(tzinfo=TZ_COLOMBIA)

        bloqueos_vencidos = self.vuelo_repo.listar_bloqueos_vencidos(ahora=now)
        bloqueos_liberados: list[str] = []
        for b in bloqueos_vencidos:
            self.vuelo_repo.liberar_bloqueo(b["idBloqueo"], motivo="vencimiento", ahora=now)
            bloqueos_liberados.append(b["idBloqueo"])

        reservas_pendientes = self.reserva_repo.listar_reservas_por_estado("Pendiente de pago")
        reservas_canceladas: list[str] = []
        for r in reservas_pendientes:
            if reserva_pendiente_esta_vencida_rn10(r, ahora=now):
                for pas in r.get("pasajeros", []):
                    id_blq = pas.get("idBloqueo")
                    if id_blq:
                        try:
                            self.vuelo_repo.liberar_bloqueo(id_blq, motivo="vencimiento", ahora=now, forzar=True)
                        except Exception:
                            pass
                self.reserva_repo.actualizar_estado_reserva(
                    codigo_pnr=r["codigoPnr"],
                    nuevo_estado="Cancelada",
                    vence_en=None,
                    motivo_cancelacion="vencimiento automático",
                )
                reservas_canceladas.append(r["codigoPnr"])
                event_bus.publish(
                    "reserva.vencida",
                    {
                        "codigoPnr": r["codigoPnr"],
                        "estadoNuevo": "Cancelada",
                        "motivo": "vencimiento automático",
                        "pasajeros": r["pasajeros"],
                        "fecha": now.isoformat(timespec="seconds"),
                    },
                )

        return {
            "bloqueosLiberados": bloqueos_liberados,
            "reservasCanceladas": reservas_canceladas,
        }

    def cancelar_reserva(
        self,
        codigo_pnr: str,
        apellido: str,
        motivo: str,
        ahora: datetime | None = None,
        tarifa_reembolsable: bool = True,
        id_reembolso_fijo: str | None = None,
    ) -> tuple[int, str, dict[str, Any]]:
        reserva = self.reserva_repo.obtener_reserva(codigo_pnr)
        requiere_reembolso, penalidad, monto_reembolso = evaluar_cancelacion_y_penalidad_rn07_rn10(
            reserva=reserva,
            apellido=apellido,
            ahora=ahora,
            tarifa_reembolsable=tarifa_reembolsable,
        )
        moneda = reserva["total"]["moneda"]

        if not requiere_reembolso:
            self.reserva_repo.actualizar_estado_reserva(
                codigo_pnr=reserva["codigoPnr"],
                nuevo_estado="Cancelada",
                saldo_pendiente=0,
                vence_en=None,
                motivo_cancelacion=motivo,
            )
            for pas in reserva.get("pasajeros", []):
                id_blq = pas.get("idBloqueo")
                if id_blq:
                    try:
                        self.vuelo_repo.liberar_bloqueo(id_blq, motivo="cancelacion", ahora=ahora, forzar=True)
                    except Exception:
                        pass
            event_bus.publish(
                "reserva.cancelada",
                {
                    "codigoPnr": reserva["codigoPnr"],
                    "estadoNuevo": "Cancelada",
                    "motivo": motivo,
                    "pasajeros": reserva["pasajeros"],
                    "fecha": (ahora or datetime.now(TZ_COLOMBIA)).isoformat(timespec="seconds"),
                },
            )
            return (
                200,
                "Reserva cancelada sin reembolso pendiente",
                {
                    "codigoPnr": reserva["codigoPnr"],
                    "estado": "Cancelada",
                    "penalidad": {"valor": penalidad, "moneda": moneda},
                    "montoReembolso": {"valor": 0, "moneda": moneda},
                    "idReembolso": None,
                    "estadoReembolso": "No aplica",
                },
            )

        self.reserva_repo.actualizar_estado_reserva(
            codigo_pnr=reserva["codigoPnr"],
            nuevo_estado="Cancelación en trámite",
            motivo_cancelacion=motivo,
        )
        tx_orig = self.reserva_repo.obtener_ultima_transaccion_aprobada(reserva["codigoPnr"])
        id_tx_orig = tx_orig["idTransaccion"] if tx_orig else "TRX-00000"
        orden = self.reserva_repo.crear_orden_reembolso(
            id_transaccion_original=id_tx_orig,
            codigo_pnr=reserva["codigoPnr"],
            penalidad_valor=penalidad,
            monto_reembolso=monto_reembolso,
            motivo=motivo,
            moneda=moneda,
            id_reembolso_fijo=id_reembolso_fijo,
        )
        return (
            202,
            "Cancelación registrada; el reembolso espera la aprobación de un segundo responsable",
            {
                "codigoPnr": reserva["codigoPnr"],
                "estado": "Cancelación en trámite",
                "penalidad": {"valor": penalidad, "moneda": moneda},
                "montoReembolso": {"valor": monto_reembolso, "moneda": moneda},
                "idReembolso": orden["idReembolso"],
                "estadoReembolso": orden["estado"],
            },
        )

    def aprobar_reembolso(
        self,
        id_reembolso: str,
        aprobador: str,
        decision: str,
        observacion: str | None = None,
    ) -> dict[str, Any]:
        reembolso = self.reserva_repo.obtener_reembolso(id_reembolso)
        nuevo_estado = validar_segundo_aprobador_reembolso_rn15(
            reembolso=reembolso,
            aprobador=aprobador,
            decision=decision,
        )
        resuelto = self.reserva_repo.resolver_reembolso(
            id_reembolso=id_reembolso,
            nuevo_estado=nuevo_estado,
            aprobador=aprobador,
            observacion=observacion,
        )
        if nuevo_estado == "ejecutado":
            event_bus.publish(
                "pago.resultado",
                {
                    "idTransaccion": resuelto["idTransaccionOriginal"],
                    "idReembolso": resuelto["idReembolso"],
                    "codigoPnr": resuelto["codigoPnr"],
                    "tipo": "reembolso",
                    "estado": "ejecutado",
                    "monto": resuelto["montoReembolso"],
                    "fecha": resuelto["fechaEjecucion"],
                },
            )
        return {
            "idReembolso": resuelto["idReembolso"],
            "codigoPnr": resuelto["codigoPnr"],
            "estado": resuelto["estado"],
            "aprobadoPor": resuelto["aprobadoPor"],
            "fechaEjecucion": resuelto["fechaEjecucion"],
        }
