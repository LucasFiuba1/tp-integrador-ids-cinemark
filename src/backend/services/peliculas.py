"""Lógica del ABM de películas importadas desde TMDB (SCRUM-52)."""
from src.backend.db import consultar, consultar_uno
from src.backend.errores import ErrorApi
from src.backend.services import tmdb

COLUMNAS = (
    "id, tmdb_id, titulo, sinopsis, poster_url, duracion_min, clasificacion, genero, "
    "disponible_desde, disponible_hasta, activa"
)


def _invalido(mensaje):
    return ErrorApi(400, "DATOS_INVALIDOS", mensaje)


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
