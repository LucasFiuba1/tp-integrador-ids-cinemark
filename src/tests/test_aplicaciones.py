"""Pruebas de integración iniciales sin servicios externos."""
from unittest.mock import patch

import requests


def test_salud(cliente_backend):
    respuesta = cliente_backend.get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"estado": "ok"}


def test_ruta_inexistente_devuelve_error_json(cliente_backend):
    respuesta = cliente_backend.get("/api/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_portada_con_api_disponible(cliente_frontend, backend_ok):
    respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    assert "<strong>ok</strong>" in respuesta.get_data(as_text=True)
    backend_ok.assert_called_once_with(
        "GET", "http://api.test/api/salud", json=None, params=None, headers={}, timeout=5
    )


def test_portada_con_api_caida(cliente_frontend):
    with patch("src.frontend.api_client.requests.request", side_effect=requests.ConnectionError):
        respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    assert "No se pudo conectar con el servidor." in respuesta.get_data(as_text=True)
