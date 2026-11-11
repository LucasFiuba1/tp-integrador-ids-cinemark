"""Pantallas del menú del header (SCRUM-95): Servicios (pública) y Mis compras (con sesión, lleva al perfil)."""
from unittest.mock import call

import pytest

from src.tests.utilidades import llamadas_sin_locales

SERVICIOS = [
    {"id": 1, "nombre": "Combo pochoclos", "descripcion": "Pochoclos grandes y gaseosa", "precio": 4500.0},
    {"id": 2, "nombre": "Estacionamiento", "descripcion": None, "precio": 3000.0},
]
ERROR_BACKEND = {"status": 503, "codigo": "BACKEND_NO_DISPONIBLE", "mensaje": "No se pudo conectar con el servidor."}


@pytest.fixture
def llamar(llamar_publico):
    llamar_publico.respuestas["/api/cartelera"] = ([{"id": 7, "titulo": "Cinema Paradiso"}], None)
    return llamar_publico


def test_servicios_muestra_los_activos_sin_sesion(cliente_frontend, llamar):
    llamar.respuestas["/api/servicios"] = (list(SERVICIOS), None)
    respuesta = cliente_frontend.get("/servicios")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "<h2>Combo pochoclos</h2>" in html and "<h2>Estacionamiento</h2>" in html
    assert "Pochoclos grandes y gaseosa" in html
    assert 'name="cantidad_' not in html  # acá solo se muestran, no se eligen
    assert call("GET", "/api/servicios") in llamadas_sin_locales(llamar)


def test_servicios_arma_los_selectores_del_header(cliente_frontend, llamar):
    llamar.respuestas["/api/servicios"] = (list(SERVICIOS), None)
    html = cliente_frontend.get("/servicios").get_data(as_text=True)
    assert '<option value="7">Cinema Paradiso</option>' in html
    assert '<option value="2">Paradiso Belgrano</option>' in html


def test_servicios_sin_ninguno_muestra_estado_vacio(cliente_frontend, llamar):
    llamar.respuestas["/api/servicios"] = ([], None)
    html = cliente_frontend.get("/servicios").get_data(as_text=True)
    assert "Por ahora no hay servicios disponibles." in html


@pytest.mark.parametrize("respuesta", [(None, ERROR_BACKEND), ({"id": 1}, None)])
def test_servicios_con_backend_caido_o_inesperado_avisa_sin_romper(cliente_frontend, llamar, respuesta):
    llamar.respuestas["/api/servicios"] = respuesta
    respuesta_http = cliente_frontend.get("/servicios")
    html = respuesta_http.get_data(as_text=True)
    assert respuesta_http.status_code == 200
    assert "No pudimos cargar los servicios." in html
    assert 'href="/servicios"' in html  # reintentar


def test_mis_compras_sin_sesion_pide_ingresar(cliente_frontend):
    respuesta = cliente_frontend.get("/mis-compras")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_mis_compras_con_sesion_lleva_a_las_compras_del_perfil(cliente_logueado):
    respuesta = cliente_logueado.get("/mis-compras")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/perfil#titulo-compras"
