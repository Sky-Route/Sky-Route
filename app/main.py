"""Punto de entrada de la aplicación FastAPI de Sky Route."""
from fastapi import FastAPI

from app.api.routers import health
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Servicios web de Sky Route: agencia de vuelos con arquitectura en capas "
                "(API, Service, Domain y Repository).",
    debug=settings.APP_DEBUG,
)

app.include_router(health.router)
