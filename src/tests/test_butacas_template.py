"""Pruebas de la pantalla de selección de butacas (SCRUM-112): grilla, leyenda, reserva y errores."""
from unittest.mock import patch

import pytest

FUNCION = {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "precio": 5000.0, "pelicula": "Volver al futuro",
           "poster_url": "https://image.tmdb.org/p.jpg", "sala": "Sala 1", "local": "Paradiso Centro"}
MAPA = {"funcion_id": 12, "sala": "Sala 1", "capacidad": 3, "libres": 2, "vendible": True, "butacas": [
    {"id": 1, "fila": "A", "numero": 1, "estado": "libre"},
    {"id": 2, "fila": "A", "numero": 2, "estado": "ocupada"},
    {"id": 3, "fila": "B", "numero": 1, "estado": "libre"},
]}


def respuestas_backend(mapa=MAPA, reserva=({"id": 88}, None)):
    """Simula llamar(...): detalle de la función, mapa de butacas y la reserva del POST."""
    def llamar(metodo, ruta, json=None, params=None):
        if metodo == "POST":
            return reserva
        return (mapa, None) if ruta.endswith("/butacas") else (FUNCION, None)
    return patch("src.frontend.routes.publico.llamar", side_effect=llamar)


@pytest.fixture
def cliente_logueado(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="token", rol="cliente", nombre="Ana")
    return cliente_frontend


def test_butacas_muestra_grilla_por_fila_leyenda_y_resumen(cliente_frontend):
    with respuestas_backend():
        respuesta = cliente_frontend.get("/funciones/12/butacas")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert '<li class="paso paso-actual" aria-current="step">' in html
    assert 'aria-label="Fila A"' in html and 'aria-label="Fila B"' in html
    assert html.count('name="butaca_ids"') == 2
    assert 'value="2"' not in html
    assert "Butaca A2: ocupada" in html
    assert "Paradiso Centro · Sala 1 · 10/11 · 20:30 · $5.000 por entrada" in html
    for dato in ("Libre", "Seleccionada", "Ocupada", "Volver al futuro", "Paradiso Centro · Sala 1", "$5.000", "2 de 3"):
        assert dato in html
    assert 'action="/funciones/12/butacas"' in html
    assert ">Continuar</button>" in html


def test_funcion_que_ya_comenzo_no_permite_elegir_butacas(cliente_frontend):
    with respuestas_backend(mapa=dict(MAPA, vendible=False)):
        html = cliente_frontend.get("/funciones/12/butacas").get_data(as_text=True)
    assert 'name="butaca_ids"' not in html
    assert ">Continuar</button>" not in html
    assert "Esta función ya comenzó" in html


def test_reservar_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.post("/funciones/12/butacas", data={"butaca_ids": ["1"]})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_reservar_butacas_libres_redirige_al_pago(cliente_logueado):
    with respuestas_backend():
        respuesta = cliente_logueado.post("/funciones/12/butacas", data={"butaca_ids": ["1", "3"]})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/compras/88/pago"


@pytest.mark.parametrize("datos", [{}, {"butaca_ids": ["x"]}, {"butaca_ids": ["0"]}])
def test_reservar_sin_butacas_validas_devuelve_400_con_mensaje(cliente_logueado, datos):
    with respuestas_backend():
        respuesta = cliente_logueado.post("/funciones/12/butacas", data=datos)
    assert respuesta.status_code == 400
    assert "Elegí al menos una butaca libre." in respuesta.get_data(as_text=True)


def test_butaca_ya_vendida_muestra_el_error_y_conserva_la_seleccion(cliente_logueado):
    error = {"status": 409, "codigo": "BUTACA_OCUPADA", "mensaje": "Las butacas B1 ya fueron vendidas."}
    with respuestas_backend(reserva=(None, error)):
        respuesta = cliente_logueado.post("/funciones/12/butacas", data={"butaca_ids": ["1", "3"]})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Las butacas B1 ya fueron vendidas." in html
    assert 'value="1" checked' in html


def test_filas_de_seis_o_mas_butacas_se_parten_con_un_pasillo(renderizar):
    butacas = [{"id": numero, "fila": "A", "numero": numero, "estado": "libre"} for numero in range(1, 13)]
    html = renderizar('{% from "macros.html" import grilla_butacas %}{{ grilla_butacas(butacas) }}', butacas=butacas)
    assert html.count("butaca-pasillo") == 1
    assert '<label class="butaca butaca-pasillo" title="A6">' in html
