"""Volver a elegir butacas con una reserva pendiente (fix-butacas): las butacas propias se ven como propias, con las
mismas se sigue con la misma compra y con otras la reserva anterior se reemplaza y se libera."""
from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

MAPA = {"funcion_id": 12, "sala": "Sala 1", "capacidad": 4, "libres": 1, "vendible": True, "butacas": [
    {"id": 1, "fila": "A", "numero": 1, "estado": "ocupada"},  # de la reserva propia
    {"id": 2, "fila": "A", "numero": 2, "estado": "ocupada"},  # de otro cliente
    {"id": 3, "fila": "B", "numero": 1, "estado": "ocupada"},  # de la reserva propia
    {"id": 4, "fila": "B", "numero": 2, "estado": "libre"},
]}
FUNCION = {"id": 12, "fecha_hora": "2099-11-10T20:30:00", "precio": 5000.0, "pelicula": "Volver al futuro",
           "poster_url": None, "sala": "Sala 1", "local": "Paradiso Centro"}
RESERVA = {"id": 88, "funcion_id": 12, "butaca_ids": [1, 3], "butacas": ["A1", "B1"], "estado": "pendiente",
           "vence_en": "2099-11-10T20:10:00"}
NUEVA = ({"id": 89, "vence_en": "2099-11-10T20:10:00"}, None)


def _api(reserva=RESERVA, nueva=NUEVA):
    def llamar(metodo, ruta, json=None, params=None):
        if metodo == "POST":
            return nueva
        if ruta.startswith("/api/compras/"):
            return (reserva, None) if reserva else (None, {"status": 404, "codigo": "NO_ENCONTRADO", "mensaje": "x"})
        return (MAPA, None) if ruta.endswith("/butacas") else (FUNCION, None)
    return patch("src.frontend.routes.publico.llamar", side_effect=llamar)


@pytest.fixture
def con_reserva(cliente_logueado):
    with cliente_logueado.session_transaction() as sesion:
        sesion["compra_id"] = 88
    return cliente_logueado


def _posts(llamar):
    return [llamada for llamada in llamar.call_args_list if llamada.args[0] == "POST"]


# --- frontend: pantalla de butacas ---
def test_al_volver_las_butacas_propias_se_ven_libres_y_elegidas(con_reserva):
    with _api():
        html = con_reserva.get("/funciones/12/butacas").get_data(as_text=True)
    assert 'value="1" checked' in html and 'value="3" checked' in html
    assert 'value="2"' not in html  # la de otro cliente sigue ocupada
    assert 'value="4"' in html and 'value="4" checked' not in html
    assert "Tenés reservadas A1, B1 hasta las 20:10." in " ".join(html.split())  # el navegador une los espacios
    assert "3 de 4" in html  # las propias cuentan como libres para este cliente


@pytest.mark.parametrize("reserva", [
    dict(RESERVA, funcion_id=99),  # reserva de otra función
    dict(RESERVA, vence_en="2020-01-01T10:00:00"),  # plazo vencido
    dict(RESERVA, estado="confirmada"),  # ya pagada
    None,  # compra inexistente o ajena
])
def test_una_reserva_que_no_corresponde_no_libera_nada(con_reserva, reserva):
    with _api(reserva=reserva):
        html = con_reserva.get("/funciones/12/butacas").get_data(as_text=True)
    assert 'value="1"' not in html and 'value="3"' not in html
    assert "Tenés reservadas" not in html


def test_sin_sesion_no_consulta_la_compra(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion["compra_id"] = 88
    with _api() as llamar:
        cliente_frontend.get("/funciones/12/butacas")
    assert not any(llamada.args[1].startswith("/api/compras/") for llamada in llamar.call_args_list)


def test_las_butacas_de_la_url_tienen_prioridad_sobre_la_reserva(con_reserva):
    with _api():
        html = con_reserva.get("/funciones/12/butacas?butaca_ids=4").get_data(as_text=True)
    assert 'value="4" checked' in html and 'value="1" checked' not in html


def test_continuar_con_las_mismas_butacas_sigue_con_la_misma_compra(con_reserva):
    with _api() as llamar:
        respuesta = con_reserva.post("/funciones/12/butacas", data={"butaca_ids": ["3", "1"]})
    assert respuesta.headers["Location"] == "/compras/88/servicios"
    assert _posts(llamar) == []  # no se reserva de nuevo: conserva servicios y plazo


def test_continuar_con_otras_butacas_crea_la_reserva_nueva(con_reserva):
    with _api() as llamar:
        respuesta = con_reserva.post("/funciones/12/butacas", data={"butaca_ids": ["1", "4"]})
    assert respuesta.headers["Location"] == "/compras/89/servicios"
    assert _posts(llamar)[0].kwargs["json"] == {"funcion_id": 12, "butaca_ids": [1, 4]}
    with con_reserva.session_transaction() as sesion:
        assert sesion["compra_id"] == 89


def test_si_la_reserva_nueva_falla_las_propias_siguen_disponibles(con_reserva):
    error = {"status": 409, "codigo": "BUTACA_OCUPADA", "mensaje": "Una o más butacas ya fueron reservadas."}
    with _api(nueva=(None, error)):
        respuesta = con_reserva.post("/funciones/12/butacas", data={"butaca_ids": ["1", "2"]})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert "Estas butacas ya no están disponibles: A2. Elegí otras." in html  # A1 es propia: no se nombra
    assert 'value="1" checked' in html


def test_el_paso_de_servicios_tiene_el_link_para_cambiar_butacas(con_reserva):
    compra = dict(RESERVA, pelicula="Volver al futuro", poster_url=None, local="Paradiso Centro", sala="Sala 1",
                  funcion="2099-11-10T20:30:00", subtotal_entradas=10000.0, servicios=[], total=10000.0)
    with patch("src.frontend.routes.publico.llamar",
               side_effect=lambda metodo, ruta, **_: ([], None) if ruta == "/api/servicios" else (compra, None)):
        html = con_reserva.get("/compras/88/servicios").get_data(as_text=True)
    assert 'href="/funciones/12/butacas">Cambiar butacas</a>' in html


# --- backend: POST /api/compras reemplaza la reserva anterior del mismo cliente ---
@pytest.fixture
def cursor():
    cursor = Mock()
    cursor.lastrowid = 5
    cursor.fetchall.side_effect = [[{"id": 28}, {"id": 63}], []]
    with patch("src.backend.services.compras.transaccion", return_value=nullcontext(cursor)):
        yield cursor


def _reservar(cliente_backend, cabeceras_cliente, cursor, vence_anterior):
    cursor.fetchone.side_effect = [{"sala_id": 1, "precio": Decimal("5500.00")}, {"vence_en": vence_anterior},
                                   {"vence_en": datetime(2099, 11, 10, 20, 10)}]
    respuesta = cliente_backend.post("/api/compras", json={"funcion_id": 7, "butaca_ids": [28, 63]},
                                     headers=cabeceras_cliente)
    assert respuesta.status_code == 201
    return [(llamada.args[0], llamada.args[1]) for llamada in cursor.execute.call_args_list]


def test_reservar_reemplaza_la_reserva_pendiente_del_mismo_cliente_antes_de_ver_las_ocupadas(
    cliente_backend, cabeceras_cliente, usuarios, cursor
):
    sentencias = _reservar(cliente_backend, cabeceras_cliente, cursor, None)
    sql = [texto for texto, _ in sentencias]
    reemplazo = sql.index("UPDATE compras SET estado = 'vencida' "
                          "WHERE usuario_id = %s AND funcion_id = %s AND estado = 'pendiente'")
    assert sentencias[reemplazo][1] == (usuarios["cliente"]["id"], 7)  # solo las del cliente, de esta función
    liberar = next(i for i, texto in enumerate(sql) if "SET e.activa = NULL" in texto)
    ocupadas = next(i for i, texto in enumerate(sql) if "FROM entradas e" in texto and "FOR UPDATE" in texto)
    assert reemplazo < liberar < ocupadas  # sus butacas se liberan antes de comprobar cuáles están ocupadas


def test_reservar_hereda_el_vencimiento_de_la_reserva_anterior(cliente_backend, cabeceras_cliente, cursor):
    anterior = datetime(2099, 11, 10, 20, 4)
    sentencias = _reservar(cliente_backend, cabeceras_cliente, cursor, anterior)
    sql, parametros = next(sentencia for sentencia in sentencias if "INSERT INTO compras" in sentencia[0])
    assert "COALESCE(%s, DATE_ADD(NOW(), INTERVAL %s MINUTE))" in sql
    assert parametros[3] == anterior


def test_reservar_sin_reserva_anterior_usa_el_plazo_completo(cliente_backend, cabeceras_cliente, cursor):
    sentencias = _reservar(cliente_backend, cabeceras_cliente, cursor, None)
    parametros = next(sentencia for sentencia in sentencias if "INSERT INTO compras" in sentencia[0])[1]
    assert parametros[3] is None and parametros[4] == 10  # COALESCE cae en NOW() + MINUTOS_RESERVA
