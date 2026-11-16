"""Service Layer: Casos de uso de búsqueda de itinerarios, mapa de asientos y bloqueos (MOD-01)."""
from datetime import date, datetime
from typing import Any

from app.domain.entities.vuelo import (
    calcular_vencimiento_bloqueo_rn01,
    filtrar_vuelos_rn04_rn05,
    validar_parametros_busqueda_itinerarios,
    validar_vuelo_con_aeronave_rn05,
)
from app.repositories.repositories.vuelo_repository import VueloRepository


class VueloService:
    def __init__(self, repository: VueloRepository | None = None):
        self.repository = repository or VueloRepository()

    def buscar_itinerarios(
        self,
        origen: str,
        destino: str,
        fecha_desde: str,
        fecha_hasta: str,
        cupos: int,
        fecha_hoy: date | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        orig, dest, f_desde, f_hasta = validar_parametros_busqueda_itinerarios(
            origen=origen,
            destino=destino,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            cupos=cupos,
            fecha_hoy=fecha_hoy,
        )
        vuelos_raw = self.repository.buscar_vuelos(
            origen=orig,
            destino=dest,
            fecha_desde=f_desde.isoformat(),
            fecha_hasta=f_hasta.isoformat(),
        )
        filtrados = filtrar_vuelos_rn04_rn05(vuelos_raw, cupos=cupos)
        itinerarios = [
            {
                "idVuelo": v["idVuelo"],
                "aerolinea": v["aerolinea"],
                "origen": v["origen"],
                "destino": v["destino"],
                "salida": v["salida"],
                "llegada": v["llegada"],
                "escalas": v["escalas"],
                "clase": v["clase"],
                "tarifa": v["tarifa"],
                "cuposDisponibles": v["cuposDisponibles"],
            }
            for v in filtrados
        ]
        if not itinerarios:
            return "No hay vuelos disponibles para los criterios indicados", []
        return "Consulta de itinerarios exitosa", itinerarios

    def consultar_mapa_asientos(self, id_vuelo: str, ahora: datetime | None = None) -> dict[str, Any]:
        vuelo = self.repository.obtener_vuelo(id_vuelo)
        validar_vuelo_con_aeronave_rn05(vuelo)
        cabinas = self.repository.obtener_mapa_asientos(id_vuelo, ahora=ahora)
        return {
            "idVuelo": vuelo["idVuelo"],
            "aeronave": {
                "modelo": vuelo["aeronave_modelo"],
                "capacidad": vuelo["aeronave_capacidad"],
            },
            "cabinas": cabinas,
        }

    def bloquear_asiento(
        self,
        id_vuelo: str,
        numero_asiento: str,
        id_sesion_compra: str,
        ahora: datetime | None = None,
        id_bloqueo_fijo: str | None = None,
    ) -> dict[str, Any]:
        creado_en, expira_en = calcular_vencimiento_bloqueo_rn01(ahora=ahora)
        return self.repository.crear_bloqueo_asiento(
            id_vuelo=id_vuelo,
            numero_asiento=numero_asiento,
            id_sesion_compra=id_sesion_compra,
            creado_en=creado_en,
            expira_en=expira_en,
            id_bloqueo_fijo=id_bloqueo_fijo,
        )

    def liberar_bloqueo(
        self,
        id_bloqueo: str,
        motivo: str = "vencimiento",
        ahora: datetime | None = None,
    ) -> dict[str, Any]:
        return self.repository.liberar_bloqueo(id_bloqueo=id_bloqueo, motivo=motivo, ahora=ahora)
