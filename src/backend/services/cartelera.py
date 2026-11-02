"""Cartelera pública y detalle de películas con sus funciones (SCRUM-20, SCRUM-21)."""
from datetime import date, datetime, timedelta

from src.backend.db import consultar, consultar_uno
from src.backend.errores import error_api
from src.backend.services.peliculas import COLUMNAS, a_json
from src.backend.services.validaciones import entero_positivo_texto

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


def _dia(texto):
    try:
        return datetime.combine(date.fromisoformat(texto), datetime.min.time())
    except ValueError:
        error_api(400, "DATOS_INVALIDOS", "fecha debe tener formato YYYY-MM-DD.")


def listar(local_id=None, fecha=None):
    """Películas con funciones vigentes y la próxima función de cada una (una fila por película)."""
    sql = (
        "SELECT peliculas.id, peliculas.titulo, peliculas.poster_url, peliculas.duracion_min, "
        "peliculas.clasificacion, peliculas.genero, MIN(funciones.fecha_hora) AS proxima_funcion"
        + FUNCIONES_VIGENTES
    )
    parametros = [datetime.now()]
    if local_id is not None:
        sql += " AND locales.id = %s"
        parametros.append(entero_positivo_texto(local_id, "local_id"))
    if fecha is not None:
        # Rango en vez de LIKE para que MySQL pueda usar el índice de fecha_hora.
        inicio = _dia(fecha)
        sql += " AND funciones.fecha_hora >= %s AND funciones.fecha_hora < %s"
        parametros += [inicio, inicio + timedelta(days=1)]
    sql += " GROUP BY peliculas.id ORDER BY proxima_funcion"

    filas = consultar(sql, parametros)
    for fila in filas:
        fila["proxima_funcion"] = fila["proxima_funcion"].isoformat()
    return filas


def obtener_pelicula(pelicula_id):
    """Película activa con sus funciones vigentes por local."""
    pelicula = consultar_uno(
        "SELECT " + COLUMNAS + " FROM peliculas WHERE id = %s AND activa = TRUE", (pelicula_id,)
    )
    if pelicula is None:
        error_api(404, "NO_ENCONTRADO", "La película no existe.")

    funciones = consultar(
        "SELECT funciones.id, funciones.fecha_hora, funciones.precio, "
        "salas.nombre AS nombre_sala, locales.nombre AS nombre_local"
        + FUNCIONES_VIGENTES
        + " AND peliculas.id = %s ORDER BY funciones.fecha_hora",
        (datetime.now(), pelicula_id),
    )
    for funcion in funciones:
        funcion["fecha_hora"] = funcion["fecha_hora"].isoformat()
        funcion["precio"] = float(funcion["precio"])

    resultado = a_json(pelicula)
    resultado["funciones"] = funciones
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
    if funcion is None:
        error_api(404, "NO_ENCONTRADO", "La función no existe.")

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
