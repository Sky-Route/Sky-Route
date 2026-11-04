# Sky Route – Servicios web

Plataforma de servicios web de una agencia de vuelos: búsqueda de itinerarios, reservas con PNR, pagos, facturación electrónica, check-in y avisos al pasajero.

## Stack

| Elemento | Tecnología |
|---|---|
| Lenguaje | Python 3.10 o superior (recomendado 3.12) |
| Framework | FastAPI |
| ORM | SQLAlchemy 2 |
| Validación | Pydantic v2 |
| Servidor | Uvicorn |
| Base de datos | SQLite en desarrollo (PostgreSQL más adelante) |

## Arquitectura en capas

Las capas son globales: cada una tiene la misma responsabilidad en los siete módulos.

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| API | `app/api/` | Expone los endpoints REST, valida el formato de entrada y responde el JSON. No aplica reglas de negocio ni toca la base de datos. |
| Service | `app/services/` | Coordina cada caso de uso, llama a otros módulos y publica eventos. No decide reglas de negocio. |
| Domain | `app/domain/` | Aplica las reglas de negocio (RN-01 a RN-35). No conoce HTTP, JSON, SQL ni proveedores externos. |
| Repository | `app/repositories/` | Guarda y consulta los datos e implementa los adaptadores de proveedores externos (Wompi, Alegra, SendGrid, Twilio). |
| Core | `app/core/` | Configuración, conexión a la base de datos y seguridad. |

Dentro de cada capa, los archivos se nombran por módulo; por ejemplo, `app/api/routers/reservas.py`, `app/services/services/reserva_service.py` y `app/repositories/repositories/reserva_repository.py`.

## Configuración del entorno (Windows, terminal de VS Code)

```powershell
python --version                        # 1. Debe ser 3.10, 3.11 o 3.12
git checkout development                # rama de trabajo
python -m venv venv                     # 2. Crear el entorno virtual
venv\Scripts\Activate.ps1               # 3. Activarlo: el prompt muestra (venv)
python -m pip install --upgrade pip     # 4. Instalar dependencias
pip install -r requirements.txt
copy .env.example .env                  # 6. Variables de entorno
uvicorn main:app --reload --port 8000   # 7. Ejecutar el servidor
```

8. Abrir <http://localhost:8000/docs> (Swagger UI), <http://localhost:8000/redoc> y <http://localhost:8000/health>.

En macOS o Linux: `source venv/bin/activate` y `cp .env.example .env`.

Si PowerShell bloquea la activación, ejecutar una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Si `python --version` muestra 3.13 o una versión más nueva, instala Python 3.12 y crea el entorno con `py -3.12 -m venv venv`. Si no es posible, instala con `pip install -r requirements-python-nuevo.txt`.

## Pruebas

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

## Ramas

`main` (producción) ← `staging` (preproducción) ← `testing` (pruebas) ← `development` (desarrollo).
