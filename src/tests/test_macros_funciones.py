"""Pruebas de los macros reutilizables de filtros y funciones (SCRUM-102)."""
from flask import render_template_string

from src.frontend.app import create_app


def test_filtro_renderiza_opciones_seleccionadas_en_formulario_get():
    app = create_app()
    opciones = [{"valor": "", "texto": "Todos"}, {"valor": "1", "texto": "Centro"}]
    with app.test_request_context("/"):
        html = render_template_string(
            '{% from "macros.html" import filtro %}'
            '<form method="get">{{ filtro("local_id", "Sucursal", opciones, "1") }}</form>',
            opciones=opciones,
        )
    assert '<form method="get">' in html
    assert '<select name="local_id">' in html
    assert '<option value="1" selected>' in html
    assert "Centro" in html


def test_chip_habilitado_enlaza_a_la_seleccion_de_butacas():
    app = create_app()
    funcion = {
        "id": 12, "fecha_hora": "2026-11-10T20:30:00", "sala": "Sala 1",
        "formato": "2D", "idioma": "Castellano", "habilitada": True,
    }
    with app.test_request_context("/"):
        html = render_template_string(
            '{% from "macros.html" import chip_funcion %}{{ chip_funcion(funcion) }}',
            funcion=funcion,
        )
    assert 'href="/funciones/12/butacas"' in html
    for dato in ("20:30", "2D", "Castellano", "Sala 1"):
        assert dato in html


def test_chip_deshabilitado_no_ofrece_enlace():
    app = create_app()
    funcion = {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "sala": "Sala 1", "habilitada": False}
    with app.test_request_context("/"):
        html = render_template_string(
            '{% from "macros.html" import chip_funcion %}{{ chip_funcion(funcion) }}',
            funcion=funcion,
        )
    assert 'aria-disabled="true"' in html
    assert "<a " not in html
    assert "Sala 1" in html
