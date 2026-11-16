"""Punto de entrada de la aplicación FastAPI de Sky Route."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routers import auth, clientes, facturas, health, operaciones, reservas, vuelos
from app.core.config import settings
from app.domain.exceptions.domain_exceptions import AppError

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Servicios web de Sky Route: agencia de vuelos con arquitectura en capas "
        "(API, Service, Domain y Repository)."
    ),
    debug=settings.APP_DEBUG,
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "mensaje": exc.mensaje,
            "data": exc.data,
            "success": False,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    for err in errors:
        loc = [str(part) for part in err.get("loc", [])]
        if "numeroDocumento" in loc or "tipoDocumento" in loc or "titular" in loc:
            return JSONResponse(
                status_code=400,
                content={
                    "mensaje": "El documento del titular es obligatorio",
                    "data": None,
                    "success": False,
                },
            )
    return JSONResponse(
        status_code=400,
        content={
            "mensaje": "Formato de solicitud no válido",
            "data": None,
            "success": False,
        },
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(vuelos.router)
app.include_router(clientes.router)
app.include_router(reservas.router)
app.include_router(facturas.router)
app.include_router(operaciones.router)
