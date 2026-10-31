"""Lógica del ABM de películas importadas desde TMDB (SCRUM-52)."""
from datetime import datetime

import pymysql

from src.backend.db import consultar, consultar_uno, ejecutar
from src.backend.errores import ErrorApi
from src.backend.services import tmdb

COLUMNAS = (
    "id, tmdb_id, titulo, sinopsis, poster_url, duracion_min, clasificacion, genero, "
    "disponible_desde, disponible_hasta, activa"
)


def _invalido(mensaje):
    return ErrorApi(400, "DATOS_INVALIDOS", mensaje)


def _leer_fecha(texto, campo):
    try:
        return datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        raise _invalido(campo + " debe tener formato YYYY-MM-DDTHH:MM:SS.")


def _validar_periodo(desde, hasta):
    if hasta <= desde:
        raise _invalido("disponible_hasta debe ser posterior a disponible_desde.")


def _a_json(fila):
    """Convierte las fechas a texto y activa a booleano para devolverlas en JSON."""
    fila["disponible_desde"] = fila["disponible_desde"].isoformat()
    fila["disponible_hasta"] = fila["disponible_hasta"].isoformat()
    fila["activa"] = bool(fila["activa"])
    return fila


def buscar_en_tmdb(texto):
    if texto is None or texto.strip() == "":
        raise _invalido("Falta el parámetro q.")
    return tmdb.buscar(texto.strip())


def listar():
    filas = consultar("SELECT " + COLUMNAS + " FROM peliculas ORDER BY titulo")
    resultado = []
    for fila in filas:
        resultado.append(_a_json(fila))
    return resultado


def obtener(pelicula_id):
    fila = consultar_uno("SELECT " + COLUMNAS + " FROM peliculas WHERE id = %s", (pelicula_id,))
    if fila is None:
        raise ErrorApi(404, "NO_ENCONTRADO", "La película no existe.")
    return _a_json(fila)


def importar(datos):
    tmdb_id = datos.get("tmdb_id")
    if type(tmdb_id) is not int or tmdb_id <= 0:
        raise _invalido("tmdb_id debe ser un entero positivo.")
    desde = _leer_fecha(datos.get("disponible_desde"), "disponible_desde")
    hasta = _leer_fecha(datos.get("disponible_hasta"), "disponible_hasta")
    _validar_periodo(desde, hasta)

    if consultar_uno("SELECT id FROM peliculas WHERE tmdb_id = %s", (tmdb_id,)) is not None:
        raise ErrorApi(409, "PELICULA_DUPLICADA", "Esa película ya fue importada.")

    pelicula = tmdb.detalle(tmdb_id)
    if pelicula["duracion_min"] <= 0 or pelicula["genero"] == "":
        raise ErrorApi(409, "PELICULA_INCOMPLETA", "TMDB no tiene duración o género de esta película.")

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
        raise ErrorApi(409, "PELICULA_DUPLICADA", "Esa película ya fue importada.")
    return obtener(nuevo_id)


def modificar(pelicula_id, datos):
    """Actualiza los campos enviados; los que no vienen quedan como estaban."""
    actual = obtener(pelicula_id)

    titulo = datos.get("titulo", actual["titulo"])
    sinopsis = datos.get("sinopsis", actual["sinopsis"])
    poster_url = datos.get("poster_url", actual["poster_url"])
    duracion_min = datos.get("duracion_min", actual["duracion_min"])
    clasificacion = datos.get("clasificacion", actual["clasificacion"])
    genero = datos.get("genero", actual["genero"])

    if type(titulo) is not str or titulo.strip() == "" or len(titulo) > 200:
        raise _invalido("titulo debe ser un texto de hasta 200 caracteres.")
    if type(genero) is not str or genero.strip() == "" or len(genero) > 50:
        raise _invalido("genero debe ser un texto de hasta 50 caracteres.")
    if type(duracion_min) is not int or duracion_min <= 0:
        raise _invalido("duracion_min debe ser un entero positivo.")
    if clasificacion is not None and (type(clasificacion) is not str or len(clasificacion) > 10):
        raise _invalido("clasificacion debe ser un texto de hasta 10 caracteres.")
    if poster_url is not None and (type(poster_url) is not str or len(poster_url) > 300):
        raise _invalido("poster_url debe ser un texto de hasta 300 caracteres.")
    if sinopsis is not None and type(sinopsis) is not str:
        raise _invalido("sinopsis debe ser un texto.")

    if "disponible_desde" in datos:
        desde = _leer_fecha(datos["disponible_desde"], "disponible_desde")
    else:
        desde = datetime.fromisoformat(actual["disponible_desde"])
    if "disponible_hasta" in datos:
        hasta = _leer_fecha(datos["disponible_hasta"], "disponible_hasta")
    else:
        hasta = datetime.fromisoformat(actual["disponible_hasta"])
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
    fila = consultar_uno("SELECT COUNT(*) AS total FROM funciones WHERE pelicula_id = %s", (pelicula_id,))
    if fila["total"] > 0:
        ejecutar("UPDATE peliculas SET activa = FALSE WHERE id = %s", (pelicula_id,))
        return {"id": pelicula_id, "baja": "logica"}
    ejecutar("DELETE FROM peliculas WHERE id = %s", (pelicula_id,))
    return {"id": pelicula_id, "baja": "fisica"}
