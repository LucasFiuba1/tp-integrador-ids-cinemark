"""Acceso a MySQL con SQL explícito y consultas parametrizadas (sin ORM).

Cada función abre su propia conexión y la cierra al terminar, así no hay
conexiones globales compartidas entre requests.
"""
from contextlib import contextmanager

import pymysql
from flask import current_app


def _conectar():
    config = current_app.config
    return pymysql.connect(
        host=config["DB_HOST"],
        port=config["DB_PORT"],
        user=config["DB_USER"],
        password=config["DB_PASSWORD"],
        database=config["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def _leer(sql, parametros, leer_filas):
    conexion = _conectar()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros or ())
            return leer_filas(cursor)
    finally:
        conexion.close()


def consultar(sql, parametros=None):
    """Ejecuta un SELECT y devuelve una lista de diccionarios."""
    return _leer(sql, parametros, lambda cursor: cursor.fetchall())


def consultar_uno(sql, parametros=None):
    """Ejecuta un SELECT y devuelve una sola fila (o None)."""
    return _leer(sql, parametros, lambda cursor: cursor.fetchone())


def ejecutar(sql, parametros=None):
    """Ejecuta un INSERT/UPDATE/DELETE y devuelve el id insertado."""
    with transaccion() as cursor:
        cursor.execute(sql, parametros or ())
        return cursor.lastrowid


@contextmanager
def transaccion():
    """Agrupa varias sentencias: commit si todo sale bien, rollback si falla.

    Uso:
        with transaccion() as cursor:
            cursor.execute("INSERT ...", (...))
            cursor.execute("UPDATE ...", (...))
    """
    conexion = _conectar()
    try:
        with conexion.cursor() as cursor:
            yield cursor
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
