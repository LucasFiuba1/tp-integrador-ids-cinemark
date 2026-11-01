"""Pruebas del ABM de películas (SCRUM-52) con la base y TMDB simulados."""
import unittest
from datetime import datetime
from unittest.mock import patch

from src.backend.app import create_app
from src.backend.auth import generar_token

PELICULA_TMDB = {
    "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "Marty viaja en el tiempo.",
    "poster_url": "https://image.tmdb.org/t/p/w500/x.jpg", "duracion_min": 116,
    "clasificacion": "PG", "genero": "Ciencia ficción",
}
PERIODO = {"disponible_desde": "2026-11-01T00:00:00", "disponible_hasta": "2026-12-15T23:59:59"}


def fila(**extra):
    base = {
        "id": 3, "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "s",
        "poster_url": None, "duracion_min": 116, "clasificacion": "PG", "genero": "Ciencia ficción",
        "disponible_desde": datetime(2026, 11, 1), "disponible_hasta": datetime(2026, 12, 15, 23, 59, 59),
        "activa": 1,
    }
    return {**base, **extra}


class PeliculasTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="pruebas")
        self.cliente = self.app.test_client()
        self.rol = "admin"
        parche = patch("src.backend.auth.consultar_uno", side_effect=self._usuario)
        parche.start()
        self.addCleanup(parche.stop)
        with self.app.app_context():
            self.cabeceras = {"Authorization": f"Bearer {generar_token(1)}"}

    def _usuario(self, sql, params=None):
        return {"id": 1, "nombre": "Admin", "rol": self.rol}

    # --- protección ---
    def test_sin_token_devuelve_401(self):
        self.assertEqual(self.cliente.get("/api/admin/peliculas").status_code, 401)

    def test_cliente_devuelve_403(self):
        self.rol = "cliente"
        respuesta = self.cliente.get("/api/admin/peliculas", headers=self.cabeceras)
        self.assertEqual(respuesta.status_code, 403)

    # --- alta ---
    @patch("src.backend.services.peliculas.ejecutar", return_value=3)
    @patch("src.backend.services.peliculas.tmdb.detalle", return_value=PELICULA_TMDB)
    @patch("src.backend.services.peliculas.consultar_uno")
    def test_alta_importa_pelicula(self, consultar_uno, detalle, ejecutar):
        consultar_uno.side_effect = [None, fila()]  # no existe; luego se relee
        respuesta = self.cliente.post(
            "/api/admin/peliculas", json={"tmdb_id": 105, **PERIODO}, headers=self.cabeceras
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.get_json()["titulo"], "Volver al futuro")
        self.assertEqual(respuesta.get_json()["disponible_desde"], "2026-11-01T00:00:00")
        ejecutar.assert_called_once()

    @patch("src.backend.services.peliculas.tmdb.detalle")
    @patch("src.backend.services.peliculas.consultar_uno", return_value={"id": 3})
    def test_alta_duplicada_devuelve_409(self, consultar_uno, detalle):
        respuesta = self.cliente.post(
            "/api/admin/peliculas", json={"tmdb_id": 105, **PERIODO}, headers=self.cabeceras
        )
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.get_json()["error"]["codigo"], "PELICULA_DUPLICADA")
        detalle.assert_not_called()

    def test_alta_con_datos_invalidos_devuelve_400(self):
        casos = [
            {"disponible_desde": PERIODO["disponible_desde"]},
            {"tmdb_id": "abc", **PERIODO},
            {"tmdb_id": 105, "disponible_desde": "ayer", "disponible_hasta": PERIODO["disponible_hasta"]},
            {"tmdb_id": 105, "disponible_desde": PERIODO["disponible_hasta"],
             "disponible_hasta": PERIODO["disponible_desde"]},
        ]
        for cuerpo in casos:
            with self.subTest(cuerpo=cuerpo):
                respuesta = self.cliente.post("/api/admin/peliculas", json=cuerpo, headers=self.cabeceras)
                self.assertEqual(respuesta.status_code, 400)

    # --- edición ---
    @patch("src.backend.services.peliculas.ejecutar")
    @patch("src.backend.services.peliculas.consultar_uno")
    def test_edicion_actualiza_periodo(self, consultar_uno, ejecutar):
        consultar_uno.side_effect = [fila(), fila(disponible_hasta=datetime(2027, 1, 31))]
        respuesta = self.cliente.patch(
            "/api/admin/peliculas/3", json={"disponible_hasta": "2027-01-31T00:00:00"},
            headers=self.cabeceras,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["disponible_hasta"], "2027-01-31T00:00:00")
        self.assertEqual(respuesta.get_json()["titulo"], "Volver al futuro")
        self.assertIn("UPDATE peliculas", ejecutar.call_args.args[0])

    @patch("src.backend.services.peliculas.consultar_uno", return_value=fila())
    def test_edicion_con_periodo_invertido_devuelve_400(self, consultar_uno):
        respuesta = self.cliente.patch(
            "/api/admin/peliculas/3", json={"disponible_hasta": "2026-10-01T00:00:00"},
            headers=self.cabeceras,
        )
        self.assertEqual(respuesta.status_code, 400)

    @patch("src.backend.services.peliculas.consultar_uno", return_value=None)
    def test_edicion_de_inexistente_devuelve_404(self, consultar_uno):
        respuesta = self.cliente.patch("/api/admin/peliculas/99", json={"titulo": "x"}, headers=self.cabeceras)
        self.assertEqual(respuesta.status_code, 404)

    def test_put_de_pelicula_devuelve_405(self):
        respuesta = self.cliente.put(
            "/api/admin/peliculas/3", json={"titulo": "x"}, headers=self.cabeceras
        )
        self.assertEqual(respuesta.status_code, 405)

    # --- baja ---
    @patch("src.backend.services.peliculas.ejecutar")
    @patch("src.backend.services.peliculas.consultar_uno")
    def test_baja_con_funciones_es_logica(self, consultar_uno, ejecutar):
        consultar_uno.side_effect = [fila(), {"total": 2}]
        respuesta = self.cliente.delete("/api/admin/peliculas/3", headers=self.cabeceras)
        self.assertEqual(respuesta.get_json()["baja"], "logica")
        self.assertIn("UPDATE peliculas SET activa = FALSE", ejecutar.call_args.args[0])

    @patch("src.backend.services.peliculas.ejecutar")
    @patch("src.backend.services.peliculas.consultar_uno")
    def test_baja_sin_funciones_es_fisica(self, consultar_uno, ejecutar):
        consultar_uno.side_effect = [fila(), {"total": 0}]
        respuesta = self.cliente.delete("/api/admin/peliculas/3", headers=self.cabeceras)
        self.assertEqual(respuesta.get_json()["baja"], "fisica")
        self.assertIn("DELETE FROM peliculas", ejecutar.call_args.args[0])

    # --- búsqueda TMDB ---
    @patch("src.backend.services.peliculas.tmdb.buscar", return_value=[{"tmdb_id": 105}])
    def test_busqueda_tmdb(self, buscar):
        respuesta = self.cliente.get("/api/admin/tmdb/buscar?q=futuro", headers=self.cabeceras)
        self.assertEqual(respuesta.get_json(), [{"tmdb_id": 105}])
        buscar.assert_called_once_with("futuro")

    def test_busqueda_sin_q_devuelve_400(self):
        respuesta = self.cliente.get("/api/admin/tmdb/buscar", headers=self.cabeceras)
        self.assertEqual(respuesta.status_code, 400)


if __name__ == "__main__":
    unittest.main()
