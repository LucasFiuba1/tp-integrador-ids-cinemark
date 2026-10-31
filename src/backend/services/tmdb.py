"""Cliente mínimo de la API de TMDB (búsqueda y detalle de películas)."""
import requests
from flask import current_app

from src.backend.errores import ErrorApi

URL_BASE = "https://api.themoviedb.org/3"
URL_POSTER = "https://image.tmdb.org/t/p/w500"
PAISES_CLASIFICACION = ("AR", "US")


def _get(ruta, **params):
    clave = current_app.config["TMDB_API_KEY"]
    if not clave:
        raise ErrorApi(502, "TMDB_NO_DISPONIBLE", "Falta configurar TMDB_API_KEY.")
    params.update(api_key=clave, language="es-AR")
    try:
        respuesta = requests.get(f"{URL_BASE}{ruta}", params=params, timeout=5)
    except requests.RequestException:
        raise ErrorApi(502, "TMDB_NO_DISPONIBLE", "No se pudo consultar TMDB.")
    if respuesta.status_code == 404:
        raise ErrorApi(404, "TMDB_NO_ENCONTRADA", "La película no existe en TMDB.")
    if not respuesta.ok:
        raise ErrorApi(502, "TMDB_NO_DISPONIBLE", "TMDB devolvió un error.")
    return respuesta.json()


def _poster(path):
    return f"{URL_POSTER}{path}" if path else None


def buscar(texto):
    """Devuelve una lista de {tmdb_id, titulo, sinopsis, poster_url, fecha_estreno}."""
    datos = _get("/search/movie", query=texto)
    resultado = []
    for p in datos.get("results", []):
        resultado.append({
            "tmdb_id": p["id"],
            "titulo": p.get("title", ""),
            "sinopsis": p.get("overview", ""),
            "poster_url": _poster(p.get("poster_path")),
            "fecha_estreno": p.get("release_date") or None,
        })
    return resultado


def _clasificacion(release_dates):
    for pais in PAISES_CLASIFICACION:
        for resultado in release_dates.get("results", []):
            if resultado["iso_3166_1"] == pais:
                for estreno in resultado["release_dates"]:
                    if estreno.get("certification"):
                        return estreno["certification"]
    return None


def detalle(tmdb_id):
    """Devuelve los datos de la película tal como se guardan en la tabla peliculas."""
    p = _get(f"/movie/{tmdb_id}", append_to_response="release_dates")
    nombres_generos = []
    for genero in p.get("genres", []):
        nombres_generos.append(genero["name"])
    return {
        "tmdb_id": p["id"],
        "titulo": p.get("title", ""),
        "sinopsis": p.get("overview") or None,
        "poster_url": _poster(p.get("poster_path")),
        "duracion_min": p.get("runtime") or 0,
        "clasificacion": _clasificacion(p.get("release_dates", {})),
        "genero": ", ".join(nombres_generos),
    }
