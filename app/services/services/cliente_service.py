"""Service Layer: Consentimientos de privacidad (MOD-07 · HU-005) y registro de pasajeros (MOD-02 · HU-006)."""
from typing import Any

from app.domain.entities.cliente import validar_consentimiento_rn35, validar_y_clasificar_pasajero_rn06
from app.domain.exceptions.domain_exceptions import AppError
from app.repositories.repositories.cliente_repository import ClienteRepository


class ClienteService:
    def __init__(self, repository: ClienteRepository | None = None):
        self.repository = repository or ClienteRepository()

    def registrar_consentimiento(
        self,
        titular: dict[str, Any] | None,
        finalidades: list[dict[str, str]],
        canal: str,
        id_consentimiento_fijo: str | None = None,
    ) -> dict[str, Any]:
        puede_continuar = validar_consentimiento_rn35(titular=titular, finalidades=finalidades, canal=canal)
        return self.repository.guardar_consentimiento(
            tipo_documento=str(titular["tipoDocumento"]).strip().upper(),
            numero_documento=str(titular["numeroDocumento"]).strip(),
            finalidades=finalidades,
            canal=canal.strip(),
            puede_continuar=puede_continuar,
            id_consentimiento_fijo=id_consentimiento_fijo,
        )

    def registrar_pasajero(
        self,
        nombres: str,
        apellidos: str,
        tipo_documento: str,
        numero_documento: str,
        fecha_nacimiento: str,
        correo: str,
        telefono: str,
        id_consentimiento: str,
        id_pasajero_fijo: str | None = None,
    ) -> dict[str, Any]:
        consentimiento = self.repository.obtener_consentimiento(id_consentimiento)
        operativa_ok = bool(consentimiento and consentimiento.get("puedeContinuarCompra"))

        tipo_pasajero = validar_y_clasificar_pasajero_rn06(
            nombres=nombres,
            apellidos=apellidos,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            fecha_nacimiento=fecha_nacimiento,
            correo=correo,
            telefono=telefono,
            consentimiento_operativo_vigente=operativa_ok,
        )

        existente = self.repository.buscar_pasajero_por_documento(numero_documento.strip())
        if existente:
            raise AppError(
                "El pasajero ya está registrado",
                status_code=409,
                data={"idPasajero": existente["idPasajero"]},
            )

        creado = self.repository.guardar_pasajero(
            nombres=nombres,
            apellidos=apellidos,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            fecha_nacimiento=fecha_nacimiento,
            correo=correo,
            telefono=telefono,
            id_consentimiento=id_consentimiento,
            tipo_pasajero=tipo_pasajero,
            id_pasajero_fijo=id_pasajero_fijo,
        )
        return {
            "idPasajero": creado["idPasajero"],
            "nombreCompleto": creado["nombreCompleto"],
            "documento": creado["documento"],
            "tipoPasajero": creado["tipoPasajero"],
        }
