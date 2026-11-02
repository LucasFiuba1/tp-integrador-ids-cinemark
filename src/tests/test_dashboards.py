"""Pruebas del template maquetado de dashboards del backoffice (SCRUM-121)."""
import unittest
from src.frontend.app import create_app as crear_frontend
from unittest.mock import patch

from src.frontend.filtros import numero
from src.frontend.routes import backoffice


def test_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/dashboards")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_muestra_los_kpi_y_los_cuatro_tableros(cliente_admin):
    respuesta = cliente_admin.get("/admin/dashboards")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/dashboards" aria-current="page"' in html
    for valor in ("1.742", "$4.820.000", "68%", "4,2%"):
        assert f'<p class="kpi-valor">{valor}</p>' in html
    for titulo in ("Entradas por franja horaria", "Ocupación por película", "Ventas por género",
                   "Cancelaciones por película"):
        assert f">{titulo}</h2>" in html


def test_las_variaciones_marcan_si_son_buenas_o_malas(cliente_admin):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert '<p class="kpi-detalle kpi-positivo">▲ 12% vs. semana anterior</p>' in html
    assert '<p class="kpi-detalle kpi-negativo">▼ 3 pts vs. semana anterior</p>' in html
    # Más cancelaciones que la semana anterior es una mala noticia aunque el número suba.
    assert '<p class="kpi-detalle kpi-negativo">▲ 0,6 pts vs. semana anterior</p>' in html


def test_la_franja_mas_vendida_se_destaca_y_las_columnas_son_proporcionales(cliente_admin):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert html.count("columna-destacada") == 1
    assert 'style="height: calc(100.0% - var(--espacio-5))"' in html
    assert 'style="height: calc(24.3% - var(--espacio-5))"' in html  # 180 de 742
    assert '<span class="columna-etiqueta">18 a 21 h</span>' in html


def test_tableros_vacios_no_rompen_la_pagina(cliente_admin):
    datos = dict(backoffice._dashboards_ejemplo(), franjas_horarias=[], ocupacion=[], ventas_genero=[],
                 cancelaciones=[])
    with patch.object(backoffice, "_dashboards_ejemplo", return_value=datos):
        respuesta = cliente_admin.get("/admin/dashboards")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert html.count("Todavía no hay datos para este período.") == 4
    assert 'class="columnas"' not in html


def test_numero_usa_formato_argentino():
    assert numero(1742) == "1.742"
    assert numero(4.2) == "4,2"
    assert numero(74) == "74"
    assert numero("sin dato") == "sin dato"
