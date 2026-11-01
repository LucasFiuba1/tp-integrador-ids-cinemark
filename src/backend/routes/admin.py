"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""

import pymysql
from flask import Blueprint, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.errores import respuesta_error
from src.backend.routes.comun import cuerpo_json
from src.backend.services import locales, peliculas, salas

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")



@admin_bp.get("/locales")
@requiere_rol("admin")
def listar_locales():
    return jsonify(locales.listar_locales())


@admin_bp.post("/locales")
@requiere_rol("admin")
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
@requiere_rol("admin")
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
@requiere_rol("admin")
def eliminar_local(local_id):
    if locales.obtener_local(local_id) is None:
        return respuesta_error(404, "NO_ENCONTRADO", "El local no existe.")
    if locales.local_tiene_salas(local_id):
        return respuesta_error(409, "LOCAL_CON_SALAS", "No se puede eliminar un local que tiene salas.")
    locales.eliminar_local(local_id)
    return "", 204


@admin_bp.get("/salas")
@requiere_rol("admin")
def listar_salas():
    local_id = request.args.get("local_id", type=int)
    return jsonify(salas.listar_salas(local_id))


@admin_bp.post("/salas")
@requiere_rol("admin")
def crear_sala():
    datos = request.get_json(silent=True) or {}
    local_id = datos.get("local_id")
    nombre = datos.get("nombre")
    filas = datos.get("filas")
    columnas = datos.get("columnas")
    mensaje = salas.validar_salas(nombre, filas, columnas)
    if mensaje:
        return respuesta_error(400, "DATOS_INVALIDOS", mensaje)
    if locales.obtener_local(local_id) is None:
        return respuesta_error(404, "NO_ENCONTRADO", "El local no existe.")
    try:
        sala = salas.crear_sala(local_id, nombre, filas, columnas)
    except pymysql.err.IntegrityError:
        return respuesta_error(409, "SALA_DUPLICADA", "Ya existe una sala con ese nombre en el local.")
    return jsonify(sala), 201


@admin_bp.put("/salas/<int:sala_id>")
@requiere_rol("admin")
def modificar_sala(sala_id):
    sala = salas.obtener_sala(sala_id)
    if sala is None:
        return respuesta_error(404, "NO_ENCONTRADO", "La sala no existe.")
    datos = request.get_json(silent=True) or {}
    nombre = datos.get("nombre")
    filas = datos.get("filas")
    columnas = datos.get("columnas")
    mensaje = salas.validar_salas(nombre, filas, columnas)
    if mensaje:
        return respuesta_error(400, "DATOS_INVALIDOS", mensaje)
    se_achica_la_sala = filas < sala["filas"] or columnas < sala["columnas"]
    if se_achica_la_sala and salas.tiene_funciones_futuras(sala_id):
        return respuesta_error(409, "SALA_CON_FUNCIONES", "No se puede reducir una sala con funciones futuras.")
    if se_achica_la_sala and salas.hay_entradas_en_butacas_eliminadas(sala_id, filas, columnas):
        return respuesta_error(409, "BUTACAS_CON_ENTRADAS", "Hay entradas vendidas en las butacas que se quitarían.")
    try:
        res = salas.modificar_sala(sala_id, nombre, filas, columnas, sala)
    except pymysql.err.IntegrityError:
        return respuesta_error(409, "SALA_DUPLICADA", "Ya existe una sala con ese nombre en el local.")
    return jsonify(res)


@admin_bp.delete("/salas/<int:sala_id>")
@requiere_rol("admin")
def eliminar_sala(sala_id):
    if salas.obtener_sala(sala_id) is None:
        return respuesta_error(404, "NO_ENCONTRADO", "La sala no existe.")
    if salas.tiene_funciones_futuras(sala_id):
        return respuesta_error(409, "SALA_CON_FUNCIONES", "No se puede dar de baja una sala con funciones futuras.")
    salas.eliminar_sala(sala_id)
    return "", 204


@admin_bp.get("/tmdb/buscar")
@requiere_rol("admin")
def buscar_tmdb():
    return jsonify(peliculas.buscar_en_tmdb(request.args.get("q")))


@admin_bp.get("/peliculas")
@requiere_rol("admin")
def listar_peliculas():
    return jsonify(peliculas.listar())


@admin_bp.post("/peliculas")
@requiere_rol("admin")
def importar_pelicula():
    return jsonify(peliculas.importar(cuerpo_json())), 201


@admin_bp.get("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def obtener_pelicula(pelicula_id):
    return jsonify(peliculas.obtener(pelicula_id))


@admin_bp.patch("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def modificar_pelicula(pelicula_id):
    return jsonify(peliculas.modificar(pelicula_id, cuerpo_json()))


@admin_bp.delete("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def eliminar_pelicula(pelicula_id):
    return jsonify(peliculas.dar_de_baja(pelicula_id))
