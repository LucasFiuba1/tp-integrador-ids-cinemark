"""Pruebas de las vistas de cartelera y detalle de película (SCRUM-59)."""
from unittest.mock import patch

import pytest

PELICULA = {
    "id": 3, "titulo": "Volver al futuro", "sinopsis": "Un viaje en el tiempo.",
    "poster_url": None, "duracion_min": 116, "clasificacion": "ATP", "genero": "Ciencia ficción",
    "funciones": [
        {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "precio": 5500.0,
         "nombre_sala": "Sala 1", "nombre_local": "Paradiso Centro"},
        {"id": 13, "fecha_hora": "2026-11-10T18:00:00", "precio": 5500.0,
         "nombre_sala": "Sala 1", "nombre_local": "Paradiso Belgrano"},
        {"id": 14, "fecha_hora": "2026-11-10T22:00:00", "precio": 6000.0,
         "nombre_sala": "Sala 2", "nombre_local": "Paradiso Centro"},
    ],
}


@pytest.fixture
def llamar():
    with patch("src.frontend.routes.publico.llamar") as llamar:
        yield llamar


def test_cartelera_muestra_grilla_y_formulario_get(cliente_frontend, llamar):
    llamar.side_effect = [
        ({"estado": "ok"}, None),
        ([{"id": 3, "titulo": "Volver al futuro", "poster_url": None,
           "duracion_min": 116, "clasificacion": "ATP", "genero": "Ciencia ficción"}], None),
    ]
    respuesta = cliente_frontend.get("/")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert '<form method="get"' in html
    assert 'name="local_id"' in html
    assert 'name="fecha"' in html
    assert 'type="date"' in html
    assert "Volver al futuro" in html
    assert 'href="/peliculas/3"' in html
    assert "Paradiso Centro" in html


def test_cartelera_envia_local_y_fecha_a_la_api(cliente_frontend, llamar):
    llamar.side_effect = [({"estado": "ok"}, None), ([], None)]
    cliente_frontend.get("/?local_id=2&fecha=2026-11-10")
    llamar.assert_any_call("GET", "/api/cartelera", params={"local_id": "2", "fecha": "2026-11-10"})


def test_cartelera_con_api_caida_muestra_aviso(cliente_frontend, llamar):
    error = {"status": 503, "codigo": "BACKEND_NO_DISPONIBLE", "mensaje": "No se pudo conectar con el servidor."}
    llamar.side_effect = [(None, error), (None, error)]
    respuesta = cliente_frontend.get("/")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "No se pudo conectar con el servidor." in html
    assert "no hay funciones disponibles" in html


def test_detalle_muestra_sinopsis_y_funciones_agrupadas_por_local(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    respuesta = cliente_frontend.get("/peliculas/3")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Un viaje en el tiempo." in html
    assert "116 min" in html
    assert "ATP" in html
    assert "Elegir butacas" in html
    assert html.count("Paradiso Centro") == 1
    assert html.find("Paradiso Belgrano") < html.find("Paradiso Centro")
    assert 'href="/funciones/12/butacas"' in html


def test_detalle_de_pelicula_inexistente_muestra_404_amigable(cliente_frontend, llamar):
    llamar.return_value = (None, {"status": 404, "codigo": "NO_ENCONTRADO", "mensaje": "La película no existe."})
    respuesta = cliente_frontend.get("/peliculas/99")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 404
    assert "No encontramos esa página" in html
    assert 'href="/">cartelera</a>' in html
