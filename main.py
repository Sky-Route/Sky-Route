"""Permite arrancar con: uvicorn main:app --reload"""
from app.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    from app.core.config import settings

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)
