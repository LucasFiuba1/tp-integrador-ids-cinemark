"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
import pymysql
from flask import Blueprint, jsonify, request

from src.backend.errores import respuesta_error
from src.backend.services import locales

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/locales")
def listar_locales():
    return jsonify(locales.list_locals())


@admin_bp.post("/locales")
def create_local_route():
    datos = request.get_json()
    nombre = datos.get("nombre")
    direccion = datos.get("direccion")
    mensaje = locales.validate_local(nombre, direccion)
    if mensaje:
        return respuesta_error(400, "DATOS_INVALIDOS", mensaje)
    try:
        local = locales.create_local_service(nombre, direccion)
    except pymysql.err.IntegrityError:
        return respuesta_error(409, "LOCAL_DUPLICADO", "Ya existe un local con ese nombre o dirección.")
    return jsonify(local), 201