"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
import pymysql
from flask import Blueprint, jsonify, request

from src.backend.errores import respuesta_error
from src.backend.services import locales, salas

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/locales")
def listar_locales():
    return jsonify(locales.listar_locales())


@admin_bp.post("/locales")
def crear_local():
    datos = request.get_json(silent=True) or {}
    nombre = datos.get("nombre")
    direccion = datos.get("direccion")
    mensaje = locales.validar_local(nombre, direccion)
    if mensaje:
        return respuesta_error(400, "DATOS_INVALIDOS", mensaje)
    try:
        local = locales.crear_local(nombre, direccion)
    except pymysql.err.IntegrityError:
        return respuesta_error(409, "LOCAL_DUPLICADO", "Ya existe un local con ese nombre o dirección.")
    return jsonify(local), 201


@admin_bp.put("/locales/<int:local_id>")
def modificar_local(local_id):
    if locales.obtener_local(local_id) is None:
        return respuesta_error(404, "NO_ENCONTRADO", "El local no existe.")
    datos = request.get_json(silent=True) or {}
    nombre = datos.get("nombre")
    direccion = datos.get("direccion")
    mensaje = locales.validar_local(nombre, direccion)
    if mensaje:
        return respuesta_error(400, "DATOS_INVALIDOS", mensaje)
    try:
        local = locales.modificar_local(local_id, nombre, direccion)
    except pymysql.err.IntegrityError:
        return respuesta_error(409, "LOCAL_DUPLICADO", "Ya existe un local con ese nombre o dirección.")
    return jsonify(local)


@admin_bp.delete("/locales/<int:local_id>")
def eliminar_local(local_id):
    if locales.obtener_local(local_id) is None:
        return respuesta_error(404, "NO_ENCONTRADO", "El local no existe.")
    if locales.local_tiene_salas(local_id):
        return respuesta_error(409, "LOCAL_CON_SALAS", "No se puede eliminar un local que tiene salas.")
    locales.eliminar_local(local_id)
    return "", 204


@admin_bp.get("/salas")
def listar_salas():
    local_id = request.args.get("local_id", type=int)
    return jsonify(salas.listar_salas(local_id))


