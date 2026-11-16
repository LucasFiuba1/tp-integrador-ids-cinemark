"""Acceso a MySQL con SQL explícito y consultas parametrizadas (sin ORM).

Cada función abre su propia conexión y la cierra al terminar, así no hay
conexiones globales compartidas entre requests.
"""
import ssl
from contextlib import contextmanager

import pymysql
from flask import current_app


def _conectar():
    config = current_app.config
    # Con DB_SSL se cifra la conexión verificando certificado y hostname contra los CA del sistema.
    opciones_tls = {"ssl": ssl.create_default_context()} if config.get("DB_SSL") else {}
    return pymysql.connect(
        host=config["DB_HOST"],
        port=config["DB_PORT"],
        user=config["DB_USER"],
        password=config["DB_PASSWORD"],
        database=config["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        **opciones_tls,
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


def marcadores(cantidad):
    """Devuelve `cantidad` marcadores `%s` separados por coma, para armar un `IN (...)` parametrizado.

    Solo genera los `%s`: los valores siempre viajan aparte, en los parámetros de `execute`.
    Ejemplo: `"... WHERE id IN (" + marcadores(3) + ")"` → `"... WHERE id IN (%s, %s, %s)"`.
    """
    return ", ".join(["%s"] * cantidad)


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
