"""Pruebas del cliente de TMDB (SCRUM-51) con requests simulado."""
import unittest
from unittest.mock import Mock, patch

import requests

from src.backend.app import create_app
from src.backend.errores import ErrorApi
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


class TmdbTest(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True, TMDB_API_KEY="clave-de-prueba")
        contexto = app.app_context()
        contexto.push()
        self.addCleanup(contexto.pop)
        self.app = app

    def assertErrorApi(self, status, codigo, funcion, *args):
        with self.assertRaises(ErrorApi) as error:
            funcion(*args)
        self.assertEqual(error.exception.status, status)
        self.assertEqual(error.exception.codigo, codigo)

    # --- búsqueda ---
    @patch("src.backend.services.tmdb.requests.get")
    def test_buscar_normaliza_resultados(self, get):
        get.return_value = respuesta(json=BUSQUEDA)
        resultado = tmdb.buscar("futuro")
        self.assertEqual(resultado[0], {
            "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "Marty viaja en el tiempo.",
            "poster_url": "https://image.tmdb.org/t/p/w500/x.jpg", "fecha_estreno": "1985-07-03",
        })
        self.assertIsNone(resultado[1]["poster_url"])
        self.assertIsNone(resultado[1]["fecha_estreno"])

    @patch("src.backend.services.tmdb.requests.get")
    def test_buscar_envia_clave_idioma_y_timeout(self, get):
        get.return_value = respuesta(json={"results": []})
        self.assertEqual(tmdb.buscar("futuro"), [])
        url = get.call_args.args[0]
        params = get.call_args.kwargs["params"]
        self.assertEqual(url, "https://api.themoviedb.org/3/search/movie")
        self.assertEqual(params, {"query": "futuro", "api_key": "clave-de-prueba", "language": "es-AR"})
        self.assertEqual(get.call_args.kwargs["timeout"], 5)

    # --- detalle ---
    @patch("src.backend.services.tmdb.requests.get")
    def test_detalle_normaliza_pelicula(self, get):
        get.return_value = respuesta(json=detalle_tmdb())
        self.assertEqual(tmdb.detalle(105), {
            "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "Marty viaja en el tiempo.",
            "poster_url": "https://image.tmdb.org/t/p/w500/x.jpg", "duracion_min": 116,
            "clasificacion": "ATP", "genero": "Ciencia ficción, Comedia",
        })
        self.assertEqual(get.call_args.args[0], "https://api.themoviedb.org/3/movie/105")
        self.assertEqual(get.call_args.kwargs["params"]["append_to_response"], "release_dates")

    @patch("src.backend.services.tmdb.requests.get")
    def test_detalle_usa_clasificacion_de_eeuu_si_no_hay_de_argentina(self, get):
        fechas = {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "PG"}]}]}
        get.return_value = respuesta(json=detalle_tmdb(release_dates=fechas))
        self.assertEqual(tmdb.detalle(105)["clasificacion"], "PG")

    @patch("src.backend.services.tmdb.requests.get")
    def test_detalle_con_datos_faltantes(self, get):
        get.return_value = respuesta(json=detalle_tmdb(
            overview="", poster_path=None, runtime=None, genres=[], release_dates={"results": []}
        ))
        pelicula = tmdb.detalle(105)
        self.assertIsNone(pelicula["sinopsis"])
        self.assertIsNone(pelicula["poster_url"])
        self.assertIsNone(pelicula["clasificacion"])
        self.assertEqual(pelicula["duracion_min"], 0)
        self.assertEqual(pelicula["genero"], "")

    # --- errores controlados ---
    @patch("src.backend.services.tmdb.requests.get")
    def test_sin_clave_devuelve_502_sin_llamar_a_tmdb(self, get):
        self.app.config["TMDB_API_KEY"] = ""
        self.assertErrorApi(502, "TMDB_NO_DISPONIBLE", tmdb.buscar, "futuro")
        get.assert_not_called()

    @patch("src.backend.services.tmdb.requests.get")
    def test_tmdb_caido_devuelve_502(self, get):
        for falla in (requests.Timeout(), requests.ConnectionError()):
            with self.subTest(falla=type(falla).__name__):
                get.side_effect = falla
                self.assertErrorApi(502, "TMDB_NO_DISPONIBLE", tmdb.detalle, 105)

    @patch("src.backend.services.tmdb.requests.get")
    def test_tmdb_con_error_devuelve_502(self, get):
        for status in (401, 429, 500):
            with self.subTest(status=status):
                get.return_value = respuesta(status)
                self.assertErrorApi(502, "TMDB_NO_DISPONIBLE", tmdb.buscar, "futuro")

    @patch("src.backend.services.tmdb.requests.get", return_value=respuesta(404))
    def test_pelicula_inexistente_devuelve_404(self, get):
        self.assertErrorApi(404, "TMDB_NO_ENCONTRADA", tmdb.detalle, 123456789)


if __name__ == "__main__":
    unittest.main()
