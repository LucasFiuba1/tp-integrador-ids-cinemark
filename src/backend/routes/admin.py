"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")
