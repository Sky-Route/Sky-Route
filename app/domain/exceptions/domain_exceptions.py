"""Excepciones de negocio y de infraestructura para desacoplar las capas."""
from typing import Any


class AppError(Exception):
    """Excepción base con código de estado HTTP semántico y carga de datos opcional."""

    def __init__(self, mensaje: str, status_code: int = 400, data: Any = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code
        self.data = data
