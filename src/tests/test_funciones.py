"""Pruebas del CRUD administrativo de funciones (SCRUM-56), sin MySQL real.

Usa las fixtures compartidas de src/tests/conftest.py y simula el cursor SQL.
"""
from contextlib import nullcontext
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

RUTA = "/api/admin/funciones"
INICIO = datetime(2099, 11, 10, 18, 0)


def datos(**cambios):
    return {
        "pelicula_id": 3,
        "sala_id": 1,
        "fecha_hora": INICIO.isoformat(),
        "precio": 5000,
        **cambios,
    }


def pelicula(**cambios):
    return {
        "duracion_min": 120,
        "disponible_desde": datetime(2099, 1, 1),
        "disponible_hasta": datetime(2100, 12, 31),
        **cambios,
    }


def detalle(**cambios):
    return {
        "id": 12, "pelicula_id": 3, "pelicula": "Volver al futuro",
        "sala_id": 1, "sala": "Sala 1", "local_id": 1, "local": "Centro",
        "fecha_hora": INICIO, "precio": Decimal("5000.00"), "activa": 1,
        **cambios,
    }


def actual(**cambios):
    return {
        "pelicula_id": 3, "sala_id": 1,
        "fecha_hora": INICIO, "precio": Decimal("5000.00"),
        **cambios,
    }


@pytest.fixture
def bd():
    """Intercepta la transacción sin abrir una conexión a MySQL."""
    cursor = MagicMock()
    cursor.lastrowid = 12
    with patch("src.backend.services.funciones.transaccion", return_value=nullcontext(cursor)) as tx, \
         patch("src.backend.services.funciones.consultar") as consultar:
        yield SimpleNamespace(cursor=cursor, tx=tx, consultar=consultar)


def simular_alta(bd, sala_id=1, conflicto=None, resultado=None):
    # SELECT sala; SELECT película; SELECT solapamiento; SELECT detalle tras INSERT.
    bd.cursor.fetchone.side_effect = [
        {"id": sala_id}, pelicula(), conflicto, detalle(sala_id=sala_id) if resultado is None else resultado,
    ]


def peticion(cliente_backend, cabeceras, metodo="POST", ruta=RUTA, cuerpo=None):
    return cliente_backend.open(
        ruta, method=metodo, json=datos() if cuerpo is None and metodo == "POST" else cuerpo,
        headers=cabeceras,
    )


# --- Protección del backoffice ---
@pytest.mark.parametrize("metodo,ruta", [
    ("GET", RUTA), ("POST", RUTA), ("PUT", RUTA + "/12"), ("DELETE", RUTA + "/12"),
])
def test_sin_token_devuelve_401(cliente_backend, metodo, ruta):
    assert cliente_backend.open(ruta, method=metodo).status_code == 401


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", RUTA), ("POST", RUTA), ("PUT", RUTA + "/12"), ("DELETE", RUTA + "/12"),
])
def test_cliente_sin_rol_admin_devuelve_403(cliente_backend, cabeceras, usuario, metodo, ruta):
    usuario["rol"] = "cliente"
    assert cliente_backend.open(ruta, method=metodo, headers=cabeceras).status_code == 403


# --- Alta y SQL de solapamiento ---
def test_crear_funcion_valida_devuelve_201(cliente_backend, cabeceras, bd):
    simular_alta(bd)
    respuesta = peticion(cliente_backend, cabeceras)
    assert respuesta.status_code == 201
    assert respuesta.get_json()["id"] == 12
    assert respuesta.get_json()["fecha_hora"] == INICIO.isoformat()
    assert any("INSERT INTO funciones" in c.args[0] for c in bd.cursor.execute.call_args_list)


def test_misma_sala_y_horarios_superpuestos_devuelve_409(cliente_backend, cabeceras, bd):
    simular_alta(bd, conflicto={"id": 8})
    respuesta = peticion(cliente_backend, cabeceras)
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "FUNCION_SUPERPUESTA"
    consultas = [c.args for c in bd.cursor.execute.call_args_list]
    solapamiento = next((sql, params) for sql, params in consultas if "TIMESTAMPADD" in sql)
    sql, parametros = solapamiento
    # La duración de la función nueva es 120 + 15 minutos.
    assert parametros == (1, INICIO + timedelta(minutes=135), 15, INICIO)
    # Los extremos son estrictos: dos intervalos contiguos no se pisan.
    assert "f.fecha_hora < %s" in sql
    assert "TIMESTAMPADD(MINUTE, p.duracion_min + %s, f.fecha_hora) > %s" in sql
    assert "f.activa = TRUE" in sql
    assert not any("INSERT INTO funciones" in c.args[0] for c in bd.cursor.execute.call_args_list)


def test_otra_sala_mismo_horario_devuelve_201(cliente_backend, cabeceras, bd):
    simular_alta(bd, sala_id=2)
    respuesta = peticion(cliente_backend, cabeceras, cuerpo=datos(sala_id=2))
    assert respuesta.status_code == 201
    sql, parametros = next(c.args for c in bd.cursor.execute.call_args_list if "TIMESTAMPADD" in c.args[0])
    assert "f.sala_id = %s" in sql
    assert parametros[0] == 2


def test_funcion_contigua_tras_15_minutos_devuelve_201(cliente_backend, cabeceras, bd):
    # Caso: la anterior va de 18:00 a 20:00, con margen hasta 20:15.
    # No hay conflicto SQL para una nueva función que empieza exactamente a las 20:15.
    simular_alta(bd)
    nuevo_inicio = INICIO + timedelta(minutes=135)
    respuesta = peticion(cliente_backend, cabeceras, cuerpo=datos(fecha_hora=nuevo_inicio.isoformat()))
    assert respuesta.status_code == 201
    sql, parametros = next(c.args for c in bd.cursor.execute.call_args_list if "TIMESTAMPADD" in c.args[0])
    assert " > %s" in sql and " < %s" in sql
    assert parametros[-1] == nuevo_inicio


@pytest.mark.parametrize("cambio", [
    {"precio": 0}, {"precio": -1}, {"precio": True}, {"precio": "5000"},
    {"precio": 12.345}, {"pelicula_id": 0}, {"sala_id": "1"},
    {"fecha_hora": "2020-01-01T12:00:00"}, {"fecha_hora": "mañana"},
])
def test_alta_con_datos_invalidos_devuelve_400(cliente_backend, cabeceras, bd, cambio):
    respuesta = peticion(cliente_backend, cabeceras, cuerpo=datos(**cambio))
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    bd.tx.assert_not_called()


def test_alta_con_campos_faltantes_devuelve_400(cliente_backend, cabeceras, bd):
    respuesta = peticion(cliente_backend, cabeceras, cuerpo={"pelicula_id": 3})
    assert respuesta.status_code == 400
    bd.tx.assert_not_called()


def test_alta_fuera_de_disponibilidad_devuelve_400(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.side_effect = [
        {"id": 1}, pelicula(disponible_hasta=datetime(2099, 11, 1)),
    ]
    respuesta = peticion(cliente_backend, cabeceras)
    assert respuesta.status_code == 400
    assert not any("INSERT INTO funciones" in c.args[0] for c in bd.cursor.execute.call_args_list)


@pytest.mark.parametrize("respuestas", [
    [None],
    [{"id": 1}, None],
])
def test_pelicula_o_sala_inexistente_devuelve_404(cliente_backend, cabeceras, bd, respuestas):
    bd.cursor.fetchone.side_effect = respuestas
    respuesta = peticion(cliente_backend, cabeceras)
    assert respuesta.status_code == 404


# --- Listado con filtros ---
def test_listar_funciones_devuelve_200(cliente_backend, cabeceras, bd):
    bd.consultar.return_value = [detalle()]
    respuesta = peticion(cliente_backend, cabeceras, metodo="GET")
    assert respuesta.status_code == 200
    assert respuesta.get_json()[0]["precio"] == 5000.0
    assert respuesta.get_json()[0]["activa"] is True


def test_listar_filtra_por_local_y_fechas(cliente_backend, cabeceras, bd):
    bd.consultar.return_value = []
    respuesta = peticion(
        cliente_backend, cabeceras, metodo="GET",
        ruta=RUTA + "?local_id=2&desde=2099-11-01T00:00:00&hasta=2099-11-30T23:59:59",
    )
    assert respuesta.status_code == 200
    sql, parametros = bd.consultar.call_args.args
    assert "s.local_id = %s" in sql and "f.fecha_hora >= %s" in sql and "f.fecha_hora <= %s" in sql
    assert parametros[0] == 2


@pytest.mark.parametrize("filtro", [
    "local_id=abc", "local_id=0", "desde=ayer",
    "desde=2099-12-01T00:00:00&hasta=2099-11-01T00:00:00",
])
def test_listar_con_filtro_invalido_devuelve_400(cliente_backend, cabeceras, bd, filtro):
    respuesta = peticion(cliente_backend, cabeceras, metodo="GET", ruta=RUTA + "?" + filtro)
    assert respuesta.status_code == 400
    bd.consultar.assert_not_called()


# --- Modificación ---
@pytest.mark.parametrize("cambio", [
    {"sala_id": 2},
    {"fecha_hora": (INICIO + timedelta(hours=2)).isoformat()},
])
def test_no_modificar_sala_ni_horario_con_entradas(cliente_backend, cabeceras, bd, cambio):
    bd.cursor.fetchone.side_effect = [actual(), {"id": 50}]
    respuesta = peticion(cliente_backend, cabeceras, metodo="PUT", ruta=RUTA + "/12", cuerpo=cambio)
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "FUNCION_CON_ENTRADAS"
    assert not any("UPDATE funciones" in c.args[0] for c in bd.cursor.execute.call_args_list)


def test_modificar_precio_con_entradas_es_valido(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.side_effect = [actual(), {"id": 50}, {"id": 1}, pelicula(), None, detalle(precio=Decimal("5500.00"))]
    respuesta = peticion(cliente_backend, cabeceras, metodo="PUT", ruta=RUTA + "/12", cuerpo={"precio": 5500})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["precio"] == 5500.0
    sql, parametros = next(c.args for c in bd.cursor.execute.call_args_list if "TIMESTAMPADD" in c.args[0])
    assert "f.id <> %s" in sql
    assert parametros[-1] == 12


def test_modificar_con_conflicto_devuelve_409(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.side_effect = [actual(), None, {"id": 1}, pelicula(), {"id": 99}]
    respuesta = peticion(cliente_backend, cabeceras, metodo="PUT", ruta=RUTA + "/12", cuerpo={"precio": 5200})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "FUNCION_SUPERPUESTA"


def test_modificar_funcion_inexistente_devuelve_404(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.return_value = None
    respuesta = peticion(cliente_backend, cabeceras, metodo="PUT", ruta=RUTA + "/999", cuerpo={"precio": 5200})
    assert respuesta.status_code == 404


# --- Baja ---
def test_eliminar_con_entradas_devuelve_409(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.side_effect = [actual(), {"id": 50}]
    respuesta = peticion(cliente_backend, cabeceras, metodo="DELETE", ruta=RUTA + "/12")
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "FUNCION_CON_ENTRADAS"
    assert not any("UPDATE funciones" in c.args[0] for c in bd.cursor.execute.call_args_list)


def test_eliminar_sin_entradas_hace_baja_logica(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.side_effect = [actual(), None]
    respuesta = peticion(cliente_backend, cabeceras, metodo="DELETE", ruta=RUTA + "/12")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": 12, "baja": "logica"}
    assert any("UPDATE funciones SET activa = FALSE" in c.args[0] for c in bd.cursor.execute.call_args_list)


def test_eliminar_inexistente_devuelve_404(cliente_backend, cabeceras, bd):
    bd.cursor.fetchone.return_value = None
    respuesta = peticion(cliente_backend, cabeceras, metodo="DELETE", ruta=RUTA + "/999")
    assert respuesta.status_code == 404
