"""Pruebas del cliente de TMDB (SCRUM-51) con requests simulado."""
from unittest.mock import Mock, patch

import pytest
import requests
from werkzeug.exceptions import HTTPException

from src.backend.services import tmdb

BUSQUEDA = {
    "results": [
        {"id": 105, "title": "Volver al futuro", "overview": "Marty viaja en el tiempo.",
         "poster_path": "/x.jpg", "release_date": "1985-07-03"},
        {"id": 999, "title": "Sin póster", "overview": "", "poster_path": None, "release_date": ""},
    ]
}


def detalle_tmdb(**extra):
    base = {
        "id": 105, "title": "Volver al futuro", "overview": "Marty viaja en el tiempo.",
        "poster_path": "/x.jpg", "runtime": 116,
        "genres": [{"id": 878, "name": "Ciencia ficción"}, {"id": 35, "name": "Comedia"}],
        "release_dates": {"results": [
            {"iso_3166_1": "US", "release_dates": [{"certification": "PG"}]},
            {"iso_3166_1": "AR", "release_dates": [{"certification": ""}, {"certification": "ATP"}]},
        ]},
    }
    return {**base, **extra}


def respuesta(status=200, json=None):
    return Mock(status_code=status, ok=200 <= status < 300, json=Mock(return_value=json or {}))


@pytest.fixture
def get(app_backend):
    with patch("src.backend.services.tmdb.requests.get") as get:
        yield get


def afirmar_error(status, codigo, funcion, *args):
    """error_api corta con una HTTPException que lleva la respuesta JSON armada."""
    with pytest.raises(HTTPException) as error:
        funcion(*args)
    respuesta = error.value.response
    assert respuesta.status_code == status
    assert respuesta.get_json()["error"]["codigo"] == codigo


# --- búsqueda ---
def test_buscar_normaliza_resultados(get):
    get.return_value = respuesta(json=BUSQUEDA)
    resultado = tmdb.buscar("futuro")
    assert resultado[0] == {
        "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "Marty viaja en el tiempo.",
        "poster_url": "https://image.tmdb.org/t/p/w500/x.jpg", "fecha_estreno": "1985-07-03",
    }
    assert resultado[1]["poster_url"] is None
    assert resultado[1]["fecha_estreno"] is None


def test_buscar_envia_clave_idioma_y_timeout(get):
    get.return_value = respuesta(json={"results": []})
    assert tmdb.buscar("futuro") == []
    assert get.call_args.args[0] == "https://api.themoviedb.org/3/search/movie"
    assert get.call_args.kwargs["params"] == {"query": "futuro", "api_key": "clave-de-prueba", "language": "es-AR"}
    assert get.call_args.kwargs["timeout"] == 5


# --- detalle ---
def test_detalle_normaliza_pelicula(get):
    get.return_value = respuesta(json=detalle_tmdb())
    assert tmdb.detalle(105) == {
        "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "Marty viaja en el tiempo.",
        "poster_url": "https://image.tmdb.org/t/p/w500/x.jpg", "duracion_min": 116,
        "clasificacion": "ATP", "genero": "Ciencia ficción, Comedia",
    }
    assert get.call_args.args[0] == "https://api.themoviedb.org/3/movie/105"
    assert get.call_args.kwargs["params"]["append_to_response"] == "release_dates"


def test_detalle_usa_clasificacion_de_eeuu_si_no_hay_de_argentina(get):
    fechas = {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "PG"}]}]}
    get.return_value = respuesta(json=detalle_tmdb(release_dates=fechas))
    assert tmdb.detalle(105)["clasificacion"] == "PG"


def test_detalle_con_datos_faltantes(get):
    get.return_value = respuesta(json=detalle_tmdb(
        overview="", poster_path=None, runtime=None, genres=[], release_dates={"results": []}
    ))
    pelicula = tmdb.detalle(105)
    assert pelicula["sinopsis"] is None
    assert pelicula["poster_url"] is None
    assert pelicula["clasificacion"] is None
    assert pelicula["duracion_min"] == 0
    assert pelicula["genero"] == ""


# --- errores controlados ---
def test_sin_clave_devuelve_502_sin_llamar_a_tmdb(app_backend, get):
    app_backend.config["TMDB_API_KEY"] = ""
    afirmar_error(502, "TMDB_NO_DISPONIBLE", tmdb.buscar, "futuro")
    get.assert_not_called()


@pytest.mark.parametrize("falla", [requests.Timeout(), requests.ConnectionError()])
def test_tmdb_caido_devuelve_502(get, falla):
    get.side_effect = falla
    afirmar_error(502, "TMDB_NO_DISPONIBLE", tmdb.detalle, 105)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_tmdb_con_error_devuelve_502(get, status):
    get.return_value = respuesta(status)
    afirmar_error(502, "TMDB_NO_DISPONIBLE", tmdb.buscar, "futuro")


def test_pelicula_inexistente_devuelve_404(get):
    get.return_value = respuesta(404)
    afirmar_error(404, "TMDB_NO_ENCONTRADA", tmdb.detalle, 123456789)
