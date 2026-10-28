"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, jsonify, request

from src.backend.services import locales

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/locales")
def listar_locales():
    return jsonify(locales.listar_locales())

@admin_bp.post("/locales")
def crear_local():
    datos = request.get_json()
    local = locales.crear_local(datos["nombre"], datos["direccion"])
    return jsonify(local), 201