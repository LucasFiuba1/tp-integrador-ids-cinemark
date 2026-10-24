"""Pruebas de integración iniciales sin servicios externos."""
import unittest
from unittest.mock import Mock, patch

import requests

from src.backend.app import create_app as crear_backend
from src.frontend.app import create_app as crear_frontend


class BackendTest(unittest.TestCase):
    def setUp(self):
        app = crear_backend()
        app.config.update(TESTING=True)
        self.cliente = app.test_client()

    def test_salud(self):
        respuesta = self.cliente.get("/api/salud")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json(), {"estado": "ok"})

    def test_ruta_inexistente_devuelve_error_json(self):
        respuesta = self.cliente.get("/api/no-existe")
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.get_json()["error"]["codigo"], "NO_ENCONTRADO")


class FrontendTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()

    @patch("src.frontend.api_client.requests.request")
    def test_portada_con_api_disponible(self, peticion):
        peticion.return_value = Mock(ok=True, content=b'{"estado":"ok"}')
        peticion.return_value.json.return_value = {"estado": "ok"}
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("<strong>ok</strong>", respuesta.get_data(as_text=True))
        peticion.assert_called_once_with(
            "GET", "http://api.test/api/salud", json=None, params=None, headers={}, timeout=5
        )

    @patch("src.frontend.api_client.requests.request", side_effect=requests.ConnectionError)
    def test_portada_con_api_caida(self, peticion):
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("No se pudo conectar con el servidor.", respuesta.get_data(as_text=True))
