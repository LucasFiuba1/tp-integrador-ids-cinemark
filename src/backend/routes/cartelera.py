"""Cartelera pública, detalle de películas, funciones y butacas (SCRUM-20, SCRUM-21).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..db import consultar
from ..services import funciones

cartelera_bp = Blueprint("cartelera", __name__, url_prefix="/api")

@cartelera_bp.route("/cartelera", methods=["GET"])
def obtener_cartelera():
    local_id = request.args.get("local_id")
    fecha = request.args.get("fecha")
    fecha_actual = datetime.now()

    sql = """
        SELECT
            peliculas.id,
            peliculas.titulo,
            peliculas.poster_url,
            peliculas.duracion_min,
            peliculas.clasificacion,
            peliculas.genero,
            funciones.fecha_hora AS proxima_funcion
        FROM peliculas
        INNER JOIN funciones
            ON peliculas.id = funciones.pelicula_id
        INNER JOIN salas
            ON funciones.sala_id = salas.id
        INNER JOIN locales
            ON salas.local_id = locales.id
        WHERE peliculas.activa = TRUE
        AND funciones.activa = TRUE
        AND salas.activa = TRUE
        AND funciones.fecha_hora >= %s
        AND peliculas.disponible_desde <= funciones.fecha_hora
        AND peliculas.disponible_hasta >= funciones.fecha_hora
    """

    if local_id is not None:
        sql += " AND locales.id = %s"
        parametros = (fecha_actual, local_id)
    else:
        parametros = (fecha_actual,)

    if fecha is not None:
        sql += " AND funciones.fecha_hora LIKE %s"
        parametros += (fecha + "%",)

    sql += " ORDER BY funciones.fecha_hora ASC"

    resultados = consultar(sql, parametros)
    cartelera = []
    ids_agregados = []

    for pelicula in resultados:
        if pelicula["id"] not in ids_agregados:
            pelicula["proxima_funcion"] = pelicula["proxima_funcion"].isoformat()
            ids_agregados.append(pelicula["id"])
            cartelera.append(pelicula)


    return jsonify(cartelera)


@cartelera_bp.route("/peliculas/<int:id>", methods=["GET"])
def obtener_pelicula(id):
    sql = """
        SELECT *
        FROM peliculas
        WHERE peliculas.id = %s
    """
    parametros = (id,)
    resultados = consultar(sql, parametros)

    if not resultados:
        return jsonify({
            "error": {
                "codigo": "PELICULA_NO_ENCONTRADA",
                "mensaje": "La pelicula solicitada no existe."
            }
        }), 404

    pelicula = resultados[0]
    pelicula["disponible_desde"] = pelicula["disponible_desde"].isoformat()
    pelicula["disponible_hasta"] = pelicula["disponible_hasta"].isoformat()

    sql_funciones = """
        SELECT
            funciones.id,
            funciones.fecha_hora,
            funciones.precio,
            salas.nombre AS nombre_sala,
            locales.nombre AS nombre_local
        FROM funciones
        INNER JOIN salas
            ON funciones.sala_id = salas.id
        INNER JOIN locales
            ON salas.local_id = locales.id
        WHERE funciones.pelicula_id = %s
        AND funciones.activa = TRUE
        AND salas.activa = TRUE
        AND funciones.fecha_hora >= %s
    """

    parametros_funciones = (id, datetime.now())
    resultados_funciones = consultar(sql_funciones, parametros_funciones)

    for funcion in resultados_funciones:
        funcion["fecha_hora"] = funcion["fecha_hora"].isoformat()
    pelicula["funciones"] = resultados_funciones

    return jsonify(pelicula), 200


@cartelera_bp.get("/funciones/<int:funcion_id>")
def obtener_funcion(funcion_id):
    return jsonify(funciones.obtener(funcion_id))


@cartelera_bp.get("/funciones/<int:funcion_id>/butacas")
def obtener_butacas(funcion_id):
    return jsonify(funciones.obtener_butacas(funcion_id))
