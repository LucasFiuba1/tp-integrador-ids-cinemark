"""Pruebas de la reserva de butacas, POST /api/compras (SCRUM-62), con la base simulada."""
from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pymysql
import pytest

RUTA = "/api/compras"
CUERPO = {"funcion_id": 7, "butaca_ids": [28, 63]}
FUNCION = {"sala_id": 1, "precio": Decimal("5500.00")}
VENCE_EN = datetime(2026, 11, 6, 11, 33, 51)


def sentencias(cursor):
    """SQL de cada cursor.execute, en orden."""
    return [llamada.args[0] for llamada in cursor.execute.call_args_list]


def inserto_compra(cursor):
    return any("INSERT INTO compras" in sql for sql in sentencias(cursor))


@pytest.fixture
def bd():
    """Cursor simulado de db.transaccion(): una función futura, butacas de su sala y ninguna ocupada."""
    cursor = Mock()
    cursor.lastrowid = 5
    cursor.fetchone.side_effect = [FUNCION, {"vence_en": VENCE_EN}]
    cursor.fetchall.side_effect = [[{"id": 28}, {"id": 63}], []]
    with patch("src.backend.services.compras.transaccion", return_value=nullcontext(cursor)) as transaccion:
        yield SimpleNamespace(cursor=cursor, transaccion=transaccion)


# --- protección ---
def test_sin_token_devuelve_401(cliente_backend):
    assert cliente_backend.post(RUTA, json=CUERPO).status_code == 401


def test_admin_devuelve_403(cliente_backend, cabeceras, usuario):
    usuario["rol"] = "admin"
    assert cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras).status_code == 403


# --- caso feliz ---
def test_reserva_ok_crea_compra_pendiente(cliente_backend, cabeceras, usuario, bd):
    usuario["rol"] = "cliente"
    respuesta = cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras)
    assert respuesta.status_code == 201
    assert respuesta.get_json() == {
        "id": 5, "estado": "pendiente", "vence_en": "2026-11-06T11:33:51", "subtotal_entradas": 11000.0,
    }
    bd.cursor.executemany.assert_called_once()
    entradas = bd.cursor.executemany.call_args.args[1]
    assert [entrada[2] for entrada in entradas] == [28, 63]


def test_reserva_toma_el_usuario_del_token(cliente_backend, cabeceras, usuario, bd):
    usuario["rol"] = "cliente"
    cliente_backend.post(RUTA, json={**CUERPO, "usuario_id": 99}, headers=cabeceras)
    insert = next(llamada for llamada in bd.cursor.execute.call_args_list if "INSERT INTO compras" in llamada.args[0])
    assert insert.args[1][0] == usuario["id"]


def test_reserva_libera_butacas_de_compras_vencidas(cliente_backend, cabeceras, usuario, bd):
    usuario["rol"] = "cliente"
    cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras)
    sql = sentencias(bd.cursor)
    assert any("UPDATE compras SET estado = 'vencida'" in consulta for consulta in sql)
    assert any("SET e.activa = NULL" in consulta for consulta in sql)


# --- 409: butacas ocupadas ---
def test_butaca_ocupada_devuelve_409_con_las_butacas(cliente_backend, cabeceras, usuario, bd):
    usuario["rol"] = "cliente"
    bd.cursor.fetchall.side_effect = [
        [{"id": 28}, {"id": 63}],
        [{"fila": "A", "numero": 1}, {"fila": "A", "numero": 2}],
    ]
    respuesta = cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras)
    assert respuesta.status_code == 409
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "BUTACA_OCUPADA"
    assert "A1, A2" in error["mensaje"]
    assert not inserto_compra(bd.cursor)


def test_butaca_ocupada_en_carrera_devuelve_409(cliente_backend, cabeceras, usuario, bd):
    """Si otra compra gana la carrera, el UNIQUE de entradas rechaza el INSERT y se responde 409."""
    usuario["rol"] = "cliente"
    bd.cursor.executemany.side_effect = pymysql.err.IntegrityError(1062, "Duplicate entry")
    respuesta = cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras)
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "BUTACA_OCUPADA"


# --- 400: datos inválidos ---
def test_butaca_de_otra_sala_devuelve_400(cliente_backend, cabeceras, usuario, bd):
    usuario["rol"] = "cliente"
    bd.cursor.fetchall.side_effect = [[{"id": 28}]]  # la 63 no es de la sala de la función
    respuesta = cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    assert not inserto_compra(bd.cursor)


@pytest.mark.parametrize("cuerpo", [
    {},
    {"funcion_id": 7},
    {"butaca_ids": [28]},
    {"funcion_id": 7, "butaca_ids": []},
    {"funcion_id": 7, "butaca_ids": 28},
    {"funcion_id": 7, "butaca_ids": [28, 28]},
    {"funcion_id": 7, "butaca_ids": ["a"]},
    {"funcion_id": 7, "butaca_ids": [-3]},
    {"funcion_id": "x", "butaca_ids": [28]},
])
def test_reserva_con_datos_invalidos_devuelve_400(cliente_backend, cabeceras, usuario, bd, cuerpo):
    usuario["rol"] = "cliente"
    respuesta = cliente_backend.post(RUTA, json=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    bd.transaccion.assert_not_called()


# --- función inexistente o ya iniciada ---
def test_funcion_pasada_devuelve_404(cliente_backend, cabeceras, usuario, bd):
    """La consulta filtra fecha_hora > NOW(): una función iniciada no se encuentra (404 según docs/endpoints.md)."""
    usuario["rol"] = "cliente"
    bd.cursor.fetchone.side_effect = [None]
    respuesta = cliente_backend.post(RUTA, json=CUERPO, headers=cabeceras)
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "NO_ENCONTRADO"
    assert "fecha_hora > NOW()" in sentencias(bd.cursor)[0]
    assert not inserto_compra(bd.cursor)