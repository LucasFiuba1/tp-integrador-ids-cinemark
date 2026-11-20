"""Base MySQL de pruebas separada de la de desarrollo (SCRUM-78).

Las pruebas contra MySQL real son opcionales: solo corren si `.env.test` (o el entorno) define la base de pruebas.
Antes de la primera prueba que la usa, la base se borra y se vuelve a crear con `schema.sql` + `seed.sql`, así cada
corrida arranca del mismo estado. Para no borrar una base de trabajo por error, el nombre tiene que terminar en
`_test` y no puede ser el `DB_NAME` del `.env`.

    cp .env.test.example .env.test      # completar host, puerto, usuario y clave del MySQL local
    python -m pytest src/tests -v       # las pruebas *_mysql.py corren; sin .env.test se saltean

Solo funciones (sin clases): leer la configuración, recrear la base y helpers de SQL para las pruebas.
"""
import os
import re
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymysql
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO_CONFIG = RAIZ / ".env.test"
SCRIPTS = (RAIZ / "src/backend/db/schema.sql", RAIZ / "src/backend/db/seed.sql")
BASE_DE_LOS_SCRIPTS = "cine_paradiso"  # nombre fijo que usan schema.sql y seed.sql
PATRON_NOMBRE = re.compile(r"^[a-z0-9_]+_test$")
CLAVES = ("PRUEBAS_DB_HOST", "PRUEBAS_DB_PORT", "PRUEBAS_DB_USER", "PRUEBAS_DB_PASSWORD", "PRUEBAS_DB_NAME")

TMDB_ID_PRUEBA = 999999001  # película que crean las fixtures; ningún id real de TMDB llega a este número

# Usuarios que carga seed.sql (ver el comentario al principio de ese archivo).
ADMIN_SEED = {"email": "admin@cineparadiso.com", "password": "admin1234"}
CLIENTES_SEED = (
    {"email": "ana@mail.com", "password": "cliente1234"},
    {"email": "juan@mail.com", "password": "cliente1234"},
)


def leer_config():
    """Config de la base de pruebas desde `.env.test`, pisada por variables de entorno; None si no está definida.

    Devuelve las claves que usa la app (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME). Corta con ValueError si el
    nombre de la base no es seguro de borrar.
    """
    valores = dotenv_values(ARCHIVO_CONFIG) if ARCHIVO_CONFIG.exists() else {}
    valores = {clave: os.environ.get(clave, valores.get(clave)) for clave in CLAVES}
    if not valores["PRUEBAS_DB_PORT"]:
        return None

    nombre = valores["PRUEBAS_DB_NAME"] or "cine_paradiso_test"
    nombre_desarrollo = dotenv_values(RAIZ / ".env").get("DB_NAME") if (RAIZ / ".env").exists() else None
    if not PATRON_NOMBRE.match(nombre) or nombre == nombre_desarrollo:
        raise ValueError(
            f"PRUEBAS_DB_NAME={nombre!r} no es válido: tiene que terminar en _test (minúsculas, números y _) "
            "y ser distinto del DB_NAME del .env, porque las pruebas la borran y la vuelven a crear."
        )
    return {
        "DB_HOST": valores["PRUEBAS_DB_HOST"] or "127.0.0.1",
        "DB_PORT": int(valores["PRUEBAS_DB_PORT"]),
        "DB_USER": valores["PRUEBAS_DB_USER"] or "root",
        "DB_PASSWORD": valores["PRUEBAS_DB_PASSWORD"] or "",
        "DB_NAME": nombre,
        "DB_SSL": False,
    }


def conectar(config, con_base=True):
    """Conexión propia de la prueba (autocommit), independiente de la que usa la app."""
    return pymysql.connect(
        host=config["DB_HOST"], port=config["DB_PORT"], user=config["DB_USER"], password=config["DB_PASSWORD"],
        database=config["DB_NAME"] if con_base else None, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


def sentencias_de(texto):
    """Separa un script SQL en sentencias: saca las líneas de comentario y corta en cada `;` de fin de línea."""
    sin_comentarios = "\n".join(linea for linea in texto.splitlines() if not linea.strip().startswith("--"))
    return [sentencia.strip() for sentencia in re.split(r";\s*$", sin_comentarios, flags=re.M) if sentencia.strip()]


def recrear_base(config):
    """Borra la base de pruebas y la vuelve a crear con schema.sql + seed.sql (cambiando el nombre de la base)."""
    nombre = config["DB_NAME"]  # ya validado por leer_config: solo [a-z0-9_]
    conexion = conectar(config, con_base=False)
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DROP DATABASE IF EXISTS `" + nombre + "`")
            for script in SCRIPTS:
                texto = script.read_text(encoding="utf-8").replace(BASE_DE_LOS_SCRIPTS, nombre)
                for sentencia in sentencias_de(texto):
                    cursor.execute(sentencia)
    finally:
        conexion.close()


@contextmanager
def conexion_con_rollback():
    """Todas las consultas del backend usan una única conexión que nunca hace commit; al salir se deshace todo.

    Sirve para pruebas que insertan datos sin dejar rastro. No sirve para concurrencia: ahí cada hilo necesita su
    propia conexión con commit real (ver la fixture `fabrica_funciones`).
    """
    from src.backend import db

    conexion = db._conectar()
    prestada = MagicMock(wraps=conexion)
    prestada.close = MagicMock()
    prestada.commit = MagicMock()
    prestada.rollback = MagicMock()
    try:
        with patch("src.backend.db._conectar", return_value=prestada):
            yield conexion
    finally:
        conexion.rollback()
        conexion.close()


def ejecutar(conexion, sql, parametros=()):
    """INSERT/UPDATE/DELETE desde la prueba; devuelve el id insertado."""
    with conexion.cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.lastrowid


def filas(conexion, sql, parametros=()):
    with conexion.cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.fetchall()


def con_token(token):
    """Cabecera Authorization para un token obtenido con login."""
    return {"Authorization": f"Bearer {token}"}


def borrar_pelicula_de_prueba(conexion, pelicula_id):
    """Borra la película de prueba y todo lo que cuelga de ella (intentos de ingreso, compras, entradas, funciones)."""
    funciones = "SELECT id FROM funciones WHERE pelicula_id = %s"
    compras = "SELECT id FROM compras WHERE funcion_id IN (" + funciones + ")"
    ejecutar(conexion, "DELETE FROM validaciones_ingreso WHERE funcion_id IN (" + funciones + ") "
                       "OR compra_id IN (" + compras + ")", (pelicula_id, pelicula_id))
    ejecutar(conexion, "DELETE FROM entradas WHERE funcion_id IN (" + funciones + ")", (pelicula_id,))
    ejecutar(conexion, "DELETE FROM compras WHERE funcion_id IN (" + funciones + ")", (pelicula_id,))
    ejecutar(conexion, "DELETE FROM funciones WHERE pelicula_id = %s", (pelicula_id,))
    ejecutar(conexion, "DELETE FROM peliculas WHERE id = %s", (pelicula_id,))
