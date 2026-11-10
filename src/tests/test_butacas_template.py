"""Pruebas de la selección de butacas (SCRUM-112) y su integración con el flujo de compra (SCRUM-63)."""
from unittest.mock import patch

import pytest

FUNCION = {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "precio": 5000.0, "pelicula": "Volver al futuro",
           "poster_url": "https://image.tmdb.org/p.jpg", "sala": "Sala 1", "local": "Paradiso Centro"}
MAPA = {"funcion_id": 12, "sala": "Sala 1", "capacidad": 3, "libres": 2, "vendible": True, "butacas": [
    {"id": 1, "fila": "A", "numero": 1, "estado": "libre"},
    {"id": 2, "fila": "A", "numero": 2, "estado": "ocupada"},
    {"id": 3, "fila": "B", "numero": 1, "estado": "libre"},
]}


def respuestas_backend(mapa=MAPA, reserva=({"id": 88, "vence_en": "2026-11-10T20:10:00"}, None)):
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


def test_reservar_butacas_libres_redirige_a_servicios_con_el_vencimiento(cliente_logueado):
    with respuestas_backend():
        respuesta = cliente_logueado.post("/funciones/12/butacas", data={"butaca_ids": ["1", "3"]})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/compras/88/servicios"
    with cliente_logueado.session_transaction() as sesion:
        assert ("exito", "Reservamos tus butacas hasta las 20:10.") in sesion["_flashes"]


@pytest.mark.parametrize("datos", [{}, {"butaca_ids": ["x"]}, {"butaca_ids": ["0"]}, {"butaca_ids": ["²"]}])
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
    assert respuesta.status_code == 409
    assert "Las butacas B1 ya fueron vendidas." in html
    assert 'value="1" checked' in html


def test_filas_de_seis_o_mas_butacas_se_parten_con_un_pasillo(renderizar):
    butacas = [{"id": numero, "fila": "A", "numero": numero, "estado": "libre"} for numero in range(1, 13)]
    html = renderizar('{% from "macros.html" import grilla_butacas %}{{ grilla_butacas(butacas) }}', butacas=butacas)
    assert html.count("butaca-pasillo") == 1
    assert '<label class="butaca butaca-pasillo" title="A6">' in html


# --- integración del flujo de compra (SCRUM-63) ---
OCUPADA_EN_CARRERA = {"status": 409, "codigo": "BUTACA_OCUPADA", "mensaje": "Una o más butacas ya fueron reservadas."}
MAPA_CON_CONFLICTO = dict(MAPA, butacas=[
    {"id": 1, "fila": "A", "numero": 1, "estado": "ocupada"},
    {"id": 2, "fila": "A", "numero": 2, "estado": "ocupada"},
    {"id": 3, "fila": "B", "numero": 1, "estado": "libre"},
])
COMPRA = {"id": 88, "estado": "pendiente", "vence_en": "2099-11-10T20:10:00", "pelicula": "Volver al futuro",
          "poster_url": None, "local": "Paradiso Centro", "sala": "Sala 1", "funcion": "2099-11-10T20:30:00",
          "butacas": ["A1", "B1"], "subtotal_entradas": 10000.0, "servicios": [], "total": 10000.0}


def _detalle_compra(*respuesta):
    return patch("src.frontend.routes.publico.llamar", return_value=respuesta)


def test_reservar_sin_sesion_vuelve_a_las_butacas_elegidas_despues_del_login(cliente_frontend):
    cliente_frontend.post("/funciones/12/butacas", data={"butaca_ids": ["1", "3"]})
    usuario = {"token": "t", "rol": "cliente", "nombre": "Ana"}
    with patch("src.frontend.routes.publico.llamar", return_value=(usuario, None)):
        respuesta = cliente_frontend.post("/ingresar", data={"email": "ana@email.com", "password": "secreta123"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/funciones/12/butacas?butaca_ids=1&butaca_ids=3"


def test_al_volver_del_login_solo_quedan_marcadas_las_butacas_libres(cliente_frontend):
    with respuestas_backend():
        html = cliente_frontend.get("/funciones/12/butacas?butaca_ids=1&butaca_ids=2").get_data(as_text=True)
    assert 'value="1" checked' in html
    assert 'value="3" checked' not in html
    assert 'value="2"' not in html


@pytest.mark.parametrize("valor", ["x", "0", "-1", "²", "9" * 5000])
def test_butacas_invalidas_en_la_url_se_ignoran(cliente_frontend, valor):
    with respuestas_backend():
        respuesta = cliente_frontend.get("/funciones/12/butacas", query_string={"butaca_ids": valor})
    assert respuesta.status_code == 200
    assert " checked" not in respuesta.get_data(as_text=True)


def test_reservar_guarda_el_compra_id_en_la_sesion(cliente_logueado):
    with respuestas_backend():
        cliente_logueado.post("/funciones/12/butacas", data={"butaca_ids": ["1"]})
    with cliente_logueado.session_transaction() as sesion:
        assert sesion["compra_id"] == 88


def test_conflicto_nombra_las_butacas_tomadas_y_conserva_las_libres(cliente_logueado):
    with respuestas_backend(mapa=MAPA_CON_CONFLICTO, reserva=(None, OCUPADA_EN_CARRERA)):
        respuesta = cliente_logueado.post("/funciones/12/butacas", data={"butaca_ids": ["1", "3"]})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert "Estas butacas ya no están disponibles: A1. Elegí otras." in html
    assert "Una o más butacas" not in html
    assert 'value="3" checked' in html
    assert 'value="1"' not in html
    with cliente_logueado.session_transaction() as sesion:
        assert "compra_id" not in sesion


def test_otro_error_de_la_reserva_muestra_el_mensaje_con_su_status(cliente_logueado):
    error = {"status": 403, "codigo": "SIN_PERMISO", "mensaje": "No tenés permiso."}
    with respuestas_backend(reserva=(None, error)):
        respuesta = cliente_logueado.post("/funciones/12/butacas", data={"butaca_ids": ["1"]})
    assert respuesta.status_code == 403
    assert "No tenés permiso." in respuesta.get_data(as_text=True)


def test_resumen_muestra_los_datos_reales_de_la_compra(cliente_logueado):
    with _detalle_compra(COMPRA, None) as llamar:
        respuesta = cliente_logueado.get("/compras/88/servicios")
    html = respuesta.get_data(as_text=True)
    llamar.assert_called_once_with("GET", "/api/compras/88")
    assert respuesta.status_code == 200
    for dato in ("Volver al futuro", "Paradiso Centro · Sala 1", "A1, B1", "2 entradas", "$10.000", "20:10"):
        assert dato in html


def test_resumen_de_compra_ajena_o_inexistente_avisa_y_vuelve_al_inicio(cliente_logueado):
    error = {"status": 403, "codigo": "SIN_PERMISO", "mensaje": "No tenés permiso sobre esta compra."}
    with _detalle_compra(None, error):
        respuesta = cliente_logueado.get("/compras/88/servicios")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    with cliente_logueado.session_transaction() as sesion:
        assert ("error", "No tenés permiso sobre esta compra.") in sesion["_flashes"]


@pytest.mark.parametrize("cambios", [
    {"vence_en": "2020-01-01T10:00:00"},
    {"estado": "vencida", "vence_en": None},
    {"estado": "confirmada", "vence_en": None},
])
def test_resumen_de_reserva_no_vigente_avisa_y_vuelve_al_inicio(cliente_logueado, cambios):
    with _detalle_compra(dict(COMPRA, **cambios), None):
        respuesta = cliente_logueado.get("/compras/88/servicios")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    with cliente_logueado.session_transaction() as sesion:
        assert ("error", "Esta reserva ya no está activa. Elegí tus butacas de nuevo.") in sesion["_flashes"]
