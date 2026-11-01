"""Lógica del ABM de películas importadas desde TMDB (SCRUM-52)."""
from datetime import datetime

import pymysql

from src.backend.db import consultar, consultar_uno, ejecutar
from src.backend.errores import error_api
from src.backend.services import tmdb

COLUMNAS = (
    "id, tmdb_id, titulo, sinopsis, poster_url, duracion_min, clasificacion, genero, "
    "disponible_desde, disponible_hasta, activa"
)


def _invalido(mensaje):
    error_api(400, "DATOS_INVALIDOS", mensaje)


def _leer_fecha(texto, campo):
    try:
        return datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        _invalido(campo + " debe tener formato YYYY-MM-DDTHH:MM:SS.")


def _validar_periodo(desde, hasta):
    if hasta <= desde:
        _invalido("disponible_hasta debe ser posterior a disponible_desde.")


def _texto(valor, campo, maximo, obligatorio=False):
    """Valida un campo de texto: None solo si no es obligatorio; si es obligatorio, no puede ser vacío."""
    if valor is None and not obligatorio:
        return valor
    if type(valor) is not str or (obligatorio and valor.strip() == "") or len(valor) > maximo:
        _invalido(f"{campo} debe ser un texto de hasta {maximo} caracteres.")
    return valor


def _fecha_o_actual(datos, actual, campo):
    if campo in datos:
        return _leer_fecha(datos[campo], campo)
    return datetime.fromisoformat(actual[campo])


def a_json(fila):
    """Convierte las fechas a texto y activa a booleano para devolverlas en JSON."""
    fila["disponible_desde"] = fila["disponible_desde"].isoformat()
    fila["disponible_hasta"] = fila["disponible_hasta"].isoformat()
    fila["activa"] = bool(fila["activa"])
    return fila


def buscar_en_tmdb(texto):
    if texto is None or texto.strip() == "":
        _invalido("Falta el parámetro q.")
    return tmdb.buscar(texto.strip())


def listar():
    return [a_json(fila) for fila in consultar("SELECT " + COLUMNAS + " FROM peliculas ORDER BY titulo")]


def obtener(pelicula_id):
    fila = consultar_uno("SELECT " + COLUMNAS + " FROM peliculas WHERE id = %s", (pelicula_id,))
    if fila is None:
        error_api(404, "NO_ENCONTRADO", "La película no existe.")
    return a_json(fila)


def importar(datos):
    tmdb_id = datos.get("tmdb_id")
    if type(tmdb_id) is not int or tmdb_id <= 0:
        _invalido("tmdb_id debe ser un entero positivo.")
    desde = _leer_fecha(datos.get("disponible_desde"), "disponible_desde")
    hasta = _leer_fecha(datos.get("disponible_hasta"), "disponible_hasta")
    _validar_periodo(desde, hasta)

    if consultar_uno("SELECT id FROM peliculas WHERE tmdb_id = %s", (tmdb_id,)) is not None:
        error_api(409, "PELICULA_DUPLICADA", "Esa película ya fue importada.")

    pelicula = tmdb.detalle(tmdb_id)
    if pelicula["duracion_min"] <= 0 or pelicula["genero"] == "":
        error_api(409, "PELICULA_INCOMPLETA", "TMDB no tiene duración o género de esta película.")

    clasificacion = pelicula["clasificacion"]
    if clasificacion is not None:
        clasificacion = clasificacion[:10]

    try:
        nuevo_id = ejecutar(
            "INSERT INTO peliculas (tmdb_id, titulo, sinopsis, poster_url, duracion_min, "
            "clasificacion, genero, disponible_desde, disponible_hasta) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                pelicula["tmdb_id"], pelicula["titulo"][:200], pelicula["sinopsis"],
                pelicula["poster_url"], pelicula["duracion_min"], clasificacion,
                pelicula["genero"][:50], desde, hasta,
            ),
        )
    except pymysql.err.IntegrityError:
        # Otro admin la importó justo antes (tmdb_id es UNIQUE)
        error_api(409, "PELICULA_DUPLICADA", "Esa película ya fue importada.")
    return obtener(nuevo_id)


def modificar(pelicula_id, datos):
    """Actualiza los campos enviados; los que no vienen quedan como estaban."""
    actual = obtener(pelicula_id)

    titulo = _texto(datos.get("titulo", actual["titulo"]), "titulo", 200, obligatorio=True)
    genero = _texto(datos.get("genero", actual["genero"]), "genero", 50, obligatorio=True)
    clasificacion = _texto(datos.get("clasificacion", actual["clasificacion"]), "clasificacion", 10)
    poster_url = _texto(datos.get("poster_url", actual["poster_url"]), "poster_url", 300)
    sinopsis = _texto(datos.get("sinopsis", actual["sinopsis"]), "sinopsis", 65535)
    duracion_min = datos.get("duracion_min", actual["duracion_min"])
    if type(duracion_min) is not int or duracion_min <= 0:
        _invalido("duracion_min debe ser un entero positivo.")

    desde = _fecha_o_actual(datos, actual, "disponible_desde")
    hasta = _fecha_o_actual(datos, actual, "disponible_hasta")
    _validar_periodo(desde, hasta)

    ejecutar(
        "UPDATE peliculas SET titulo = %s, sinopsis = %s, poster_url = %s, duracion_min = %s, "
        "clasificacion = %s, genero = %s, disponible_desde = %s, disponible_hasta = %s "
        "WHERE id = %s",
        (titulo, sinopsis, poster_url, duracion_min, clasificacion, genero, desde, hasta, pelicula_id),
    )
    return obtener(pelicula_id)


def dar_de_baja(pelicula_id):
    """Baja lógica si la película tiene funciones asociadas; física si no."""
    obtener(pelicula_id)
    fila = consultar_uno(
        "SELECT EXISTS(SELECT 1 FROM funciones WHERE pelicula_id = %s) AS tiene_funciones", (pelicula_id,)
    )
    if fila["tiene_funciones"]:
        ejecutar("UPDATE peliculas SET activa = FALSE WHERE id = %s", (pelicula_id,))
        return {"id": pelicula_id, "baja": "logica"}
    ejecutar("DELETE FROM peliculas WHERE id = %s", (pelicula_id,))
    return {"id": pelicula_id, "baja": "fisica"}
