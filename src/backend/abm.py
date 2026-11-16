"""Helpers comunes de los ABM del backend: existencia, baja lógica y duplicados (SCRUM-100).

Los usan los CRUD de películas, locales, salas, funciones y servicios para no repetir la misma lógica en cada uno.

Los nombres de tabla y de columna salen solo de TABLAS_CON_BAJA_LOGICA, una lista blanca fija: nunca del request.
Los valores viajan siempre como parámetros `%s`.
"""
from contextlib import contextmanager

import pymysql

from src.backend import db
from src.backend.errores import error_api

# Tabla -> columna que marca si el registro está vigente. `locales` no está: no tiene baja lógica.
TABLAS_CON_BAJA_LOGICA = {
    "peliculas": "activa",
    "salas": "activa",
    "funciones": "activa",
    "servicios": "activo",
}

CLAVE_DUPLICADA = 1062  # código de error de MySQL para un UNIQUE repetido


def _columna_activa(tabla):
    """Columna de estado de `tabla`; corta con ValueError si la tabla no está en la lista blanca (error de programación)."""
    if tabla not in TABLAS_CON_BAJA_LOGICA:
        raise ValueError(f"La tabla {tabla!r} no admite baja lógica.")
    return TABLAS_CON_BAJA_LOGICA[tabla]


def requerir_existente(fila, mensaje):
    """Devuelve `fila` o corta con 404 NO_ENCONTRADO si es None (para el resultado de un consultar_uno)."""
    if fila is None:
        error_api(404, "NO_ENCONTRADO", mensaje)
    return fila


def obtener_activo(tabla, registro_id, mensaje):
    """Devuelve {"id": ...} del registro activo de `tabla`, o corta con 404 NO_ENCONTRADO si no existe o está de baja."""
    sql = "SELECT id FROM " + tabla + " WHERE id = %s AND " + _columna_activa(tabla) + " = TRUE"
    return requerir_existente(db.consultar_uno(sql, (registro_id,)), mensaje)


def _cambiar_estado(tabla, registro_id, activo):
    """`activo` es un bool del código (nunca del request): se escribe como TRUE/FALSE literal."""
    estado = "TRUE" if activo else "FALSE"
    sql = "UPDATE " + tabla + " SET " + _columna_activa(tabla) + " = " + estado + " WHERE id = %s"
    db.ejecutar(sql, (registro_id,))


def dar_de_baja_logica(tabla, registro_id):
    """Pone `activa`/`activo` en FALSE sin borrar la fila, así se conserva el historial que la referencia."""
    _cambiar_estado(tabla, registro_id, False)


def reactivar(tabla, registro_id):
    """Vuelve a poner `activa`/`activo` en TRUE."""
    _cambiar_estado(tabla, registro_id, True)


def es_clave_duplicada(error):
    """True si el IntegrityError de MySQL es por un UNIQUE repetido (y no, por ejemplo, por una clave foránea)."""
    return bool(error.args) and error.args[0] == CLAVE_DUPLICADA


@contextmanager
def traducir_duplicado(mensaje, codigo="DUPLICADO"):
    """Convierte un UNIQUE repetido dentro del bloque en 409 `codigo`; cualquier otro error sigue de largo.

    Uso:
        with traducir_duplicado("Ya existe un servicio con ese nombre.", "SERVICIO_DUPLICADO"):
            servicio_id = db.ejecutar("INSERT INTO servicios ...", (...))
    """
    try:
        yield
    except pymysql.err.IntegrityError as error:
        if es_clave_duplicada(error):
            error_api(409, codigo, mensaje)
        raise
