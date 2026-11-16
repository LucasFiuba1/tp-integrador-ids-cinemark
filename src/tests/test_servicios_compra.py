"""Pruebas de PUT /api/compras/<id>/servicios (SCRUM-64): servicios de una compra pendiente y recálculo del total."""
from decimal import Decimal

import pytest

from src.tests.utilidades import ID_CLIENTE, afirmar_error_json, simular_bd

RUTA = "/api/compras/88/servicios"
SERVICIOS_ACTIVOS = [{"id": 1, "precio": Decimal("6500.00")}, {"id": 2, "precio": Decimal("2500.00")}]
ENTRADAS = [{"precio": Decimal("5000.00")}, {"precio": Decimal("5000.00")}]
PEDIDO = [{"servicio_id": 1, "cantidad": 2}, {"servicio_id": 2, "cantidad": 1}]


def _fila_compra(**cambios):
    fila = {"id": 88, "usuario_id": ID_CLIENTE, "estado": "pendiente", "total": Decimal("10000.00"), "vencida": 0}
    fila.update(cambios)
    return fila


@pytest.fixture
def bd():
    with simular_bd(destinos=("src.backend.services.compras",)) as simulacion:
        simulacion.cursor.fetchone.return_value = _fila_compra()
        yield simulacion


def _sentencias(bd):
    return [llamada.args[0] for llamada in bd.cursor.execute.call_args_list]


def _definir(cliente_backend, cabeceras_cliente, cuerpo):
    return cliente_backend.put(RUTA, json=cuerpo, headers=cabeceras_cliente)


# --- seguridad ---
def test_definir_servicios_sin_token_devuelve_401(cliente_backend):
    afirmar_error_json(cliente_backend.put(RUTA, json=PEDIDO), 401, "NO_AUTENTICADO")


def test_definir_servicios_con_rol_admin_devuelve_403(cliente_backend, cabeceras_admin):
    afirmar_error_json(cliente_backend.put(RUTA, json=PEDIDO, headers=cabeceras_admin), 403, "SIN_PERMISO")


# --- validaciones del cuerpo ---
@pytest.mark.parametrize("cuerpo", [
    {"servicio_id": 1, "cantidad": 2},  # objeto en vez de lista
    "combo", 5, None,
    [5], [[1, 2]],  # elementos que no son objetos
    [{"servicio_id": 1}], [{"cantidad": 1}],
    [{"servicio_id": 0, "cantidad": 1}], [{"servicio_id": -1, "cantidad": 1}],
    [{"servicio_id": "1", "cantidad": 1}], [{"servicio_id": 1.5, "cantidad": 1}],
    [{"servicio_id": True, "cantidad": 1}],
    [{"servicio_id": 1, "cantidad": 0}], [{"servicio_id": 1, "cantidad": -2}],
    [{"servicio_id": 1, "cantidad": 21}], [{"servicio_id": 1, "cantidad": "2"}],
    [{"servicio_id": 1, "cantidad": 1.0}], [{"servicio_id": 1, "cantidad": True}],
    [{"servicio_id": 1, "cantidad": 1}, {"servicio_id": 1, "cantidad": 2}],  # servicio repetido
    [{"servicio_id": numero, "cantidad": 1} for numero in range(1, 52)],  # más de 50 servicios distintos
])
def test_definir_servicios_con_cuerpo_invalido_devuelve_400_sin_tocar_la_base(
    cliente_backend, cabeceras_cliente, bd, cuerpo
):
    afirmar_error_json(_definir(cliente_backend, cabeceras_cliente, cuerpo), 400, "DATOS_INVALIDOS")
    bd.transaccion.assert_not_called()


def test_definir_servicios_sin_cuerpo_json_devuelve_400(cliente_backend, cabeceras_cliente, bd):
    respuesta = cliente_backend.put(RUTA, data="no es json", headers=cabeceras_cliente)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")


def test_definir_servicios_acepta_la_cantidad_maxima(cliente_backend, cabeceras_cliente, bd):
    guardados = [{"cantidad": 20, "precio_unitario": Decimal("6500.00")}]
    bd.cursor.fetchall.side_effect = [SERVICIOS_ACTIVOS[:1], ENTRADAS, guardados]
    respuesta = _definir(cliente_backend, cabeceras_cliente, [{"servicio_id": 1, "cantidad": 20}])
    assert respuesta.status_code == 200
    assert respuesta.get_json()["total"] == 140000.0  # 10.000 de entradas + 20 x 6.500


@pytest.mark.parametrize("activos", [[], SERVICIOS_ACTIVOS[:1]])
def test_definir_servicios_inexistente_o_inactivo_devuelve_400_sin_cambiar_la_compra(
    cliente_backend, cabeceras_cliente, bd, activos
):
    bd.cursor.fetchall.side_effect = [activos]
    afirmar_error_json(_definir(cliente_backend, cabeceras_cliente, PEDIDO), 400, "DATOS_INVALIDOS")
    assert not any(sql.startswith(("DELETE", "UPDATE")) for sql in _sentencias(bd))
    bd.cursor.executemany.assert_not_called()


# --- estado de la compra ---
def test_definir_servicios_de_compra_inexistente_devuelve_404(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = None
    afirmar_error_json(_definir(cliente_backend, cabeceras_cliente, PEDIDO), 404, "NO_ENCONTRADO")


def test_definir_servicios_de_compra_ajena_devuelve_403(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_compra(usuario_id=999)
    afirmar_error_json(_definir(cliente_backend, cabeceras_cliente, PEDIDO), 403, "SIN_PERMISO")


@pytest.mark.parametrize("estado", ["confirmada", "cancelada", "vencida"])
def test_definir_servicios_de_compra_no_pendiente_devuelve_409(cliente_backend, cabeceras_cliente, bd, estado):
    bd.cursor.fetchone.return_value = _fila_compra(estado=estado)
    afirmar_error_json(_definir(cliente_backend, cabeceras_cliente, PEDIDO), 409, "COMPRA_NO_PENDIENTE")


def test_definir_servicios_con_reserva_vencida_libera_butacas_y_devuelve_409(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_compra(vencida=1)
    afirmar_error_json(_definir(cliente_backend, cabeceras_cliente, PEDIDO), 409, "RESERVA_VENCIDA")
    sentencias = _sentencias(bd)
    assert any("UPDATE compras SET estado = 'vencida'" in sql for sql in sentencias)
    assert any("UPDATE entradas SET activa = NULL" in sql for sql in sentencias)
    assert not any("compra_servicios" in sql for sql in sentencias)


# --- caso feliz ---
def test_definir_servicios_guarda_el_precio_vigente_y_devuelve_el_total(cliente_backend, cabeceras_cliente, bd):
    guardados = [{"cantidad": 2, "precio_unitario": Decimal("6500.00")},
                 {"cantidad": 1, "precio_unitario": Decimal("2500.00")}]
    bd.cursor.fetchall.side_effect = [SERVICIOS_ACTIVOS, ENTRADAS, guardados]
    respuesta = _definir(cliente_backend, cabeceras_cliente, PEDIDO)

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": 88, "total": 25500.0}  # 2 x 5.000 + 2 x 6.500 + 2.500

    sql_insert, filas = bd.cursor.executemany.call_args.args
    assert "INSERT INTO compra_servicios (compra_id, servicio_id, cantidad, precio_unitario)" in sql_insert
    assert filas == [(88, 1, 2, Decimal("6500.00")), (88, 2, 1, Decimal("2500.00"))]
    sql_update, parametros = bd.cursor.execute.call_args_list[-1].args
    assert sql_update == "UPDATE compras SET total = %s WHERE id = %s"
    assert parametros == (Decimal("25500.00"), 88)


def test_definir_servicios_reemplaza_los_anteriores_y_consulta_solo_activos(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchall.side_effect = [SERVICIOS_ACTIVOS, ENTRADAS, []]
    _definir(cliente_backend, cabeceras_cliente, PEDIDO)
    consulta_servicios = bd.cursor.execute.call_args_list[1].args
    assert consulta_servicios == ("SELECT id, precio FROM servicios WHERE activo = TRUE AND id IN (%s, %s)", (1, 2))
    sentencias = _sentencias(bd)
    assert sentencias.index("DELETE FROM compra_servicios WHERE compra_id = %s") < len(sentencias) - 1
    assert "FOR UPDATE" in sentencias[0]


def test_definir_lista_vacia_quita_los_servicios_y_deja_el_total_de_entradas(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchall.side_effect = [ENTRADAS, []]
    respuesta = _definir(cliente_backend, cabeceras_cliente, [])

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": 88, "total": 10000.0}
    sentencias = _sentencias(bd)
    assert "DELETE FROM compra_servicios WHERE compra_id = %s" in sentencias
    assert not any("FROM servicios" in sql for sql in sentencias)
    bd.cursor.executemany.assert_not_called()
