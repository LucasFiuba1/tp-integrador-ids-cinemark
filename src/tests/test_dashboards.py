"""Pruebas de los dashboards del backoffice (SCRUM-121 maqueta, SCRUM-77 datos de la API)."""
from unittest.mock import patch

import pytest

from src.frontend.filtros import numero

# Respuestas de ejemplo de GET /api/admin/dashboards/<tablero> (ver docs/endpoints.md).
RESPUESTAS = {
    "/api/admin/dashboards/franjas-horarias": [
        {"franja": "12 a 15 h", "entradas": 180}, {"franja": "15 a 18 h", "entradas": 310},
        {"franja": "18 a 21 h", "entradas": 742}, {"franja": "21 a 24 h", "entradas": 510},
    ],
    "/api/admin/dashboards/ocupacion": {
        "por_pelicula": [
            {"pelicula": "La noche del telón", "vendidas": 412, "capacidad": 560, "ocupacion": 73.6},
            {"pelicula": "Código Medianoche", "vendidas": 330, "capacidad": 500, "ocupacion": 66},
        ],
        "por_funcion": [],
    },
    "/api/admin/dashboards/ventas-genero": [
        {"genero": "Drama", "entradas": 1000, "monto": 2750000.00},
        {"genero": "Animación", "entradas": 742, "monto": 2070000.00},
    ],
    "/api/admin/dashboards/cancelaciones": [
        {"pelicula": "Código Medianoche", "compras": 300, "cancelaciones": 18, "porcentaje": 6},
        {"pelicula": "La noche del telón", "compras": 200, "cancelaciones": 3, "porcentaje": 1.5},
    ],
    "/api/admin/locales": [{"id": 1, "nombre": "Paradiso Centro", "direccion": "Av. Corrientes 1234"}],
}


@pytest.fixture
def api(request):
    """Simula llamar(...) de la ruta con RESPUESTAS (o las que pase la prueba con indirect)."""
    respuestas = getattr(request, "param", RESPUESTAS)
    with patch("src.frontend.routes.backoffice.llamar",
               side_effect=lambda metodo, ruta, params=None: (respuestas.get(ruta), None)) as llamar:
        yield llamar


def test_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/dashboards")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_muestra_los_kpi_y_los_cuatro_tableros(cliente_admin, api):
    respuesta = cliente_admin.get("/admin/dashboards")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/dashboards" aria-current="page"' in html
    # 742 / 1060 butacas y 21 / 500 compras, sumando las respuestas de la API.
    for valor in ("1.742", "$4.820.000", "70%", "4,2%"):
        assert f'<p class="kpi-valor">{valor}</p>' in html
    for titulo in ("Entradas por franja horaria", "Ocupación por película", "Ventas por género",
                   "Cancelaciones por película", "Ocupación por función"):
        assert f">{titulo}</h2>" in html


def test_la_franja_mas_vendida_se_destaca_y_las_columnas_son_proporcionales(cliente_admin, api):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert html.count("columna-destacada") == 1
    assert 'style="height: calc(100.0% - var(--espacio-5))"' in html
    assert 'style="height: calc(24.3% - var(--espacio-5))"' in html  # 180 de 742
    assert '<span class="columna-etiqueta">18 a 21 h</span>' in html


@pytest.mark.parametrize("api", [{}], indirect=True)
def test_tableros_vacios_no_rompen_la_pagina(cliente_admin, api):
    respuesta = cliente_admin.get("/admin/dashboards")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert html.count("Todavía no hay datos para este período.") == 5
    assert 'class="columnas"' not in html


def test_numero_usa_formato_argentino():
    assert numero(1742) == "1.742"
    assert numero(4.2) == "4,2"
    assert numero(74) == "74"
    assert numero("sin dato") == "sin dato"
