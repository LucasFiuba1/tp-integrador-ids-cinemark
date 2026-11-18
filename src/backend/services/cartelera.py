"""Cartelera pública y detalle de películas con sus funciones (SCRUM-20, SCRUM-21)."""
from datetime import datetime

from src.backend.abm import requerir_existente
from src.backend.db import consultar, consultar_uno
from src.backend.serializacion import serializar, serializar_lista
from src.backend.services.peliculas import COLUMNAS
from src.backend.filtros import construir_condiciones

# Funciones que se pueden vender: activas, en salas activas, futuras y dentro del período de la película.
FUNCIONES_VIGENTES = """
    FROM funciones
    INNER JOIN salas ON funciones.sala_id = salas.id
    INNER JOIN locales ON salas.local_id = locales.id
    INNER JOIN peliculas ON funciones.pelicula_id = peliculas.id
    WHERE peliculas.activa = TRUE
    AND funciones.activa = TRUE
    AND salas.activa = TRUE
    AND funciones.fecha_hora >= %s
    AND funciones.fecha_hora BETWEEN peliculas.disponible_desde AND peliculas.disponible_hasta
"""
FILTROS_CARTELERA = {"local_id": ("locales.id", "entero"), "fecha": ("funciones.fecha_hora", "dia")}


def listar(argumentos):
    """Películas con funciones vigentes y la próxima función de cada una (una fila por película).

    argumentos: query params (`local_id`, `fecha`); uno vacío da 400, como antes de SCRUM-106.
    """
    clausulas, filtros = construir_condiciones(argumentos, FILTROS_CARTELERA)
    sql = (
        "SELECT peliculas.id, peliculas.titulo, peliculas.poster_url, peliculas.duracion_min, "
        "peliculas.clasificacion, peliculas.genero, MIN(funciones.fecha_hora) AS proxima_funcion"
        + FUNCIONES_VIGENTES + clausulas
        + " GROUP BY peliculas.id ORDER BY proxima_funcion"
    )
    filas = consultar(sql, [datetime.now(), *filtros])
    return serializar_lista(filas)


def obtener_pelicula(pelicula_id):
    """Película activa con sus funciones vigentes por local."""
    pelicula = consultar_uno(
        "SELECT " + COLUMNAS + " FROM peliculas WHERE id = %s AND activa = TRUE", (pelicula_id,)
    )
    requerir_existente(pelicula, "La película no existe.")

    funciones = consultar(
        "SELECT funciones.id, funciones.fecha_hora, funciones.precio, "
        "salas.nombre AS nombre_sala, locales.id AS local_id, locales.nombre AS nombre_local"
        + FUNCIONES_VIGENTES
        + " AND peliculas.id = %s ORDER BY funciones.fecha_hora",
        (datetime.now(), pelicula_id),
    )
    
    resultado = serializar(pelicula)
    resultado["funciones"] = serializar_lista(funciones)
    return resultado


def mapa_de_butacas(funcion_id):
    """Butacas de la sala de una función con su estado (libre u ocupada), sin datos de los compradores."""
    ahora = datetime.now()
    funcion = consultar_uno(
        "SELECT funciones.id, funciones.fecha_hora, salas.nombre AS sala "
        "FROM funciones INNER JOIN salas ON funciones.sala_id = salas.id "
        "WHERE funciones.id = %s AND funciones.activa = TRUE AND salas.activa = TRUE",
        (funcion_id,),
    )
    requerir_existente(funcion, "La función no existe.")

    # Ocupa la butaca una entrada vigente de una compra confirmada o pendiente sin vencer.
    # Las de compras canceladas o vencidas no matchean el LEFT JOIN y la butaca queda libre.
    butacas = consultar(
        "SELECT butacas.id, butacas.fila, butacas.numero, "
        "IF(compras.id IS NULL, 'libre', 'ocupada') AS estado "
        "FROM funciones "
        "INNER JOIN butacas ON butacas.sala_id = funciones.sala_id "
        "LEFT JOIN entradas ON entradas.funcion_id = funciones.id "
        "AND entradas.butaca_id = butacas.id AND entradas.activa = 1 "
        "LEFT JOIN compras ON compras.id = entradas.compra_id "
        "AND (compras.estado = 'confirmada' OR (compras.estado = 'pendiente' AND compras.vence_en > %s)) "
        "WHERE funciones.id = %s "
        "ORDER BY butacas.fila, butacas.numero",
        (ahora, funcion_id),
    )
    return {
        "funcion_id": funcion["id"],
        "sala": funcion["sala"],
        "capacidad": len(butacas),
        "libres": sum(1 for butaca in butacas if butaca["estado"] == "libre"),
        "vendible": funcion["fecha_hora"] > ahora,
        "butacas": butacas,
    }
