"""Parámetros de seguridad. La emisión y validación del token JWT se construye en HU-001."""
from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
