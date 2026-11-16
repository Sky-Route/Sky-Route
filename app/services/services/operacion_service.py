"""Service Layer: Estado operativo de vuelos, alertas a pasajeros, check-in y pases de abordaje (HU-014 a HU-018)."""
from datetime import datetime
from typing import Any

from app.domain.entities.operacion import (
    TZ_COLOMBIA,
    calcular_ventana_checkin_rn16,
    construir_alerta_operativa_rn27,
    generar_codigo_qr_firmado_hu018,
    validar_checkin_en_linea_rn16,
    validar_permiso_operaciones_hu014,
    validar_transicion_estatus_vuelo_hu014,
)
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.repositories.cliente_repository import ClienteRepository
from app.repositories.repositories.operacion_repository import OperacionRepository
from app.repositories.repositories.reserva_repository import ReservaRepository
from app.repositories.repositories.vuelo_repository import VueloRepository
from app.services.events.event_bus import event_bus


class OperacionService:
    # Reloj de referencia por defecto para pruebas de ventana de check-in de VU-1023 (2026-11-19 10:00:00-05:00)
    RELOJ_ACTUAL: datetime = datetime(2026, 11, 19, 10, 0, 0, tzinfo=TZ_COLOMBIA)

    def __init__(
        self,
        operacion_repo: OperacionRepository | None = None,
        vuelo_repo: VueloRepository | None = None,
        reserva_repo: ReservaRepository | None = None,
        cliente_repo: ClienteRepository | None = None,
    ):
        self.operacion_repo = operacion_repo or OperacionRepository()
        self.vuelo_repo = vuelo_repo or VueloRepository()
        self.reserva_repo = reserva_repo or ReservaRepository()
        self.cliente_repo = cliente_repo or ClienteRepository()
        event_bus.subscribe("vuelo.estatus.cambiado", self._on_vuelo_estatus_cambiado)
        event_bus.subscribe("pase.generado", self._on_pase_generado)

    def actualizar_estatus_vuelo(
        self,
        id_vuelo: str,
        estado_nuevo: str,
        puerta: str | None = None,
        hora_estimada_salida: str | None = None,
        fuente: str = "aerolinea",
        observacion: str | None = None,
        alcance_token: list[str] | None = None,
        id_evento_fijo: str | None = None,
    ) -> dict[str, Any]:
        validar_permiso_operaciones_hu014(alcance_token)
        vuelo = self.vuelo_repo.obtener_vuelo(id_vuelo)
        if not vuelo:
            raise AppError("El vuelo indicado no existe", status_code=404)

        estatus_actual = self.operacion_repo.obtener_o_inicializar_estatus_vuelo(vuelo)
        validar_transicion_estatus_vuelo_hu014(
            id_vuelo=id_vuelo,
            estado_actual=estatus_actual["estado"],
            estado_nuevo=estado_nuevo,
        )

        puerta_final = puerta or estatus_actual["puerta"]
        hora_est_final = hora_estimada_salida or estatus_actual["horaEstimadaSalida"]
        actualizado_en = datetime.now(TZ_COLOMBIA).isoformat(timespec="seconds")

        cambio = self.operacion_repo.guardar_cambio_estatus_vuelo(
            id_vuelo=id_vuelo,
            hora_programada_salida=vuelo["salida"],
            estado_anterior=estatus_actual["estado"],
            estado_nuevo=estado_nuevo,
            puerta=puerta_final,
            hora_estimada_salida=hora_est_final,
            fuente=fuente,
            observacion=observacion,
            actualizado_en=actualizado_en,
            id_evento=id_evento_fijo,
        )

        event_bus.publish("vuelo.estatus.cambiado", cambio)

        return {
            "idVuelo": cambio["idVuelo"],
            "estadoAnterior": cambio["estadoAnterior"],
            "estadoNuevo": cambio["estadoNuevo"],
            "puerta": cambio["puerta"],
            "horaEstimadaSalida": cambio["horaEstimadaSalida"],
            "actualizadoEn": cambio["actualizadoEn"],
        }

    def consultar_estatus_vuelo(self, id_vuelo: str) -> dict[str, Any]:
        vuelo = self.vuelo_repo.obtener_vuelo(id_vuelo)
        if not vuelo:
            raise AppError("El vuelo indicado no existe", status_code=404)
        return self.operacion_repo.obtener_o_inicializar_estatus_vuelo(vuelo)

    def _on_vuelo_estatus_cambiado(self, evento: dict[str, Any]) -> None:
        id_evento = str(evento.get("idEvento") or "EVT-DEFAULT")
        id_vuelo = str(evento.get("idVuelo") or "")
        estado_nuevo = str(evento.get("estadoNuevo") or "")
        puerta = str(evento.get("puerta") or "B12")
        hora_estimada = str(evento.get("horaEstimadaSalida") or "")

        vuelo = self.vuelo_repo.obtener_vuelo(id_vuelo)
        if not vuelo:
            return

        # Identificar reservas activas (Confirmada o Facturada) de ese vuelo (FUN-113)
        reservas_activas = (
            self.reserva_repo.listar_reservas_por_estado("Confirmada")
            + self.reserva_repo.listar_reservas_por_estado("Facturada")
        )
        reservas_vuelo = [r for r in reservas_activas if r.get("idVuelo") == id_vuelo]

        for r in reservas_vuelo:
            for pas in r.get("pasajeros", []):
                id_pas = pas.get("idPasajero")
                if not id_pas or self.operacion_repo.alerta_ya_registrada(id_evento, id_pas):
                    continue
                ficha = self.cliente_repo.obtener_pasajero(id_pas)
                correo = (ficha.get("correo") or "").strip() if ficha else ""
                telefono = (ficha.get("telefono") or "").strip() if ficha else ""
                canal_preferido = (ficha.get("canalPreferido") or "correo") if ficha else "correo"
                mensaje, canal = construir_alerta_operativa_rn27(
                    id_vuelo=id_vuelo,
                    origen=vuelo["origen"],
                    destino=vuelo["destino"],
                    estado_nuevo=estado_nuevo,
                    puerta=puerta,
                    hora_estimada_salida=hora_estimada,
                    canal_preferido=canal_preferido,
                )
                self.operacion_repo.enviar_y_guardar_alerta(
                    id_evento=id_evento,
                    id_pasajero=id_pas,
                    id_vuelo=id_vuelo,
                    tipo_cambio=estado_nuevo,
                    mensaje=mensaje,
                    canal=canal,
                    correo_destino=correo,
                    telefono_destino=telefono,
                )

    def consultar_alertas_pasajero(self, id_pasajero: str) -> dict[str, Any]:
        ficha = self.cliente_repo.obtener_pasajero(id_pasajero)
        alertas = self.operacion_repo.listar_alertas_pasajero(id_pasajero)
        if not ficha and not alertas:
            raise AppError(
                "El pasajero no existe",
                status_code=404,
                data={"idPasajero": id_pasajero},
            )
        return {
            "idPasajero": id_pasajero,
            "alertas": alertas,
        }

    def consultar_ventana_checkin(self, id_vuelo: str, ahora: datetime | None = None) -> dict[str, Any]:
        vuelo = self.vuelo_repo.obtener_vuelo(id_vuelo)
        if not vuelo:
            raise AppError("El vuelo indicado no existe", status_code=404)
        reloj = ahora or self.RELOJ_ACTUAL
        ventana = calcular_ventana_checkin_rn16(hora_salida_iso=vuelo["salida"], ahora=reloj)
        return {
            "idVuelo": id_vuelo,
            **ventana,
        }

    def realizar_checkin(
        self,
        codigo_pnr: str,
        id_pasajero: str,
        id_vuelo: str,
        ahora: datetime | None = None,
    ) -> dict[str, Any]:
        vuelo = self.vuelo_repo.obtener_vuelo(id_vuelo)
        if not vuelo:
            raise AppError("El vuelo indicado no existe", status_code=404)

        pnr = (codigo_pnr or "").strip().upper()
        reserva = self.reserva_repo.obtener_reserva(pnr)
        reloj = ahora or self.RELOJ_ACTUAL

        pasajero_res = validar_checkin_en_linea_rn16(
            reserva=reserva,
            id_pasajero=id_pasajero,
            id_vuelo=id_vuelo,
            hora_salida_iso=vuelo["salida"],
            ahora=reloj,
        )

        previo = self.operacion_repo.obtener_checkin(pnr, id_pasajero, id_vuelo)
        if previo:
            raise AppError("El pasajero ya realizó el check-in en este vuelo", status_code=409)

        ficha = self.cliente_repo.obtener_pasajero(id_pasajero)
        correo = ficha["correo"] if ficha else "pasajero@correo.com"
        nombre = pasajero_res.get("nombre") or (ficha["nombreCompleto"] if ficha else id_pasajero)
        asiento = pasajero_res["asiento"]

        estatus = self.operacion_repo.obtener_o_inicializar_estatus_vuelo(vuelo)
        vuelo_pase = {
            "idVuelo": vuelo["idVuelo"],
            "origen": vuelo["origen"],
            "destino": vuelo["destino"],
            "salida": vuelo["salida"],
            "puerta": estatus["puerta"],
        }
        codigo_qr = generar_codigo_qr_firmado_hu018(
            codigo_pnr=pnr,
            id_pasajero=id_pasajero,
            id_vuelo=id_vuelo,
            asiento=asiento,
        )
        chk_data, pase_data = self.operacion_repo.guardar_checkin_y_pase(
            codigo_pnr=pnr,
            id_pasajero=id_pasajero,
            nombre_pasajero=nombre,
            correo_pasajero=correo,
            id_vuelo=id_vuelo,
            vuelo_info=vuelo_pase,
            asiento=asiento,
            codigo_qr=codigo_qr,
            fecha_checkin=reloj.isoformat(timespec="seconds"),
        )

        event_bus.publish(
            "pase.generado",
            {
                "idPaseAbordaje": pase_data["idPaseAbordaje"],
                "codigoPnr": pnr,
                "idPasajero": id_pasajero,
                "correo": correo,
                "urlPdf": pase_data["urlPdf"],
                "version": 1,
            },
        )
        return chk_data

    def _on_pase_generado(self, evento: dict[str, Any]) -> None:
        id_pab = str(evento.get("idPaseAbordaje") or "")
        correo = str(evento.get("correo") or "")
        url_pdf = str(evento.get("urlPdf") or "")
        if not id_pab:
            return
        envio = self.operacion_repo.sendgrid.enviar_correo(
            destinatario=correo,
            asunto=f"Tu pase de abordaje Sky Route ({id_pab})",
            contenido=f"Descarga tu pase de abordaje en: {url_pdf}",
        )
        self.operacion_repo.actualizar_envio_pase(id_pab, envio["estadoEntrega"])

    def consultar_pase_abordaje(self, codigo_pnr: str, id_pasajero: str) -> dict[str, Any]:
        pnr = (codigo_pnr or "").strip().upper()
        reserva = self.reserva_repo.obtener_reserva(pnr)
        if not reserva:
            raise AppError("No se encontró un pase para los datos indicados", status_code=404)

        pertenece = any(p.get("idPasajero") == id_pasajero for p in reserva.get("pasajeros", []))
        if not pertenece:
            raise AppError("No se encontró un pase para los datos indicados", status_code=404)

        pase = self.operacion_repo.obtener_pase_abordaje(pnr, id_pasajero)
        if not pase:
            raise AppError(
                "El pase de abordaje se genera después del check-in",
                status_code=409,
                data={"codigoPnr": pnr, "idPasajero": id_pasajero},
            )
        return pase


operacion_service_listener = OperacionService()
