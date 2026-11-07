"""Pruebas del ABM de servicios con baja lógica y del listado público (SCRUM-71). Base simulada, sin MySQL."""
from decimal import Decimal
from unittest.mock import patch

import pymysql
import pytest

from src.tests.utilidades import afirmar_error_json

SERVICIO_NUEVO = {"nombre": "Combo familiar", "descripcion": "Dos pochoclos y dos gaseosas", "precio": 9500}


def fila(id=1, nombre="Gaseosa", precio="2500.00", activo=1):
    """Fila tal como la devuelve MySQL: precio DECIMAL y activo como entero."""
    return {"id": id, "nombre": nombre, "descripcion": "Gaseosa de 500 ml", "precio": Decimal(precio), "activo": activo}


@pytest.fixture
def db():
    with patch("src.backend.services.servicios.db") as db_simulada:
        db_simulada.ejecutar.return_value = 9
        yield db_simulada


def duplicado():
    return pymysql.err.IntegrityError(1062, "Duplicate entry")


# --- seguridad ---
RUTAS_ADMIN = (
    ("GET", "/api/admin/servicios"), ("POST", "/api/admin/servicios"),
    ("PUT", "/api/admin/servicios/1"), ("DELETE", "/api/admin/servicios/1"),
)


@pytest.mark.parametrize("metodo, ruta", RUTAS_ADMIN)
def test_rutas_admin_sin_token_devuelven_401(cliente_backend, db, metodo, ruta):
    respuesta = cliente_backend.open(ruta, method=metodo, json=SERVICIO_NUEVO)
    assert respuesta.status_code == 401
    db.ejecutar.assert_not_called()


@pytest.mark.parametrize("metodo, ruta", RUTAS_ADMIN)
def test_rutas_admin_con_rol_cliente_devuelven_403(cliente_backend, cabeceras_cliente, db, metodo, ruta):
    respuesta = cliente_backend.open(ruta, method=metodo, json=SERVICIO_NUEVO, headers=cabeceras_cliente)
    afirmar_error_json(respuesta, 403, "SIN_PERMISO")
    db.ejecutar.assert_not_called()


# --- listados ---
def test_listar_admin_devuelve_activos_e_inactivos_con_precio_numerico(cliente_backend, cabeceras_admin, db):
    db.consultar.return_value = [fila(), fila(id=4, nombre="Acceso VIP", precio="8000.00", activo=0)]
    respuesta = cliente_backend.get("/api/admin/servicios", headers=cabeceras_admin)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [
        {"id": 1, "nombre": "Gaseosa", "descripcion": "Gaseosa de 500 ml", "precio": 2500.0, "activo": True},
        {"id": 4, "nombre": "Acceso VIP", "descripcion": "Gaseosa de 500 ml", "precio": 8000.0, "activo": False},
    ]
    assert "activo = TRUE" not in db.consultar.call_args.args[0]


def test_listar_publico_sin_token_filtra_los_inactivos_en_sql(cliente_backend, db):
    db.consultar.return_value = [fila()]
    respuesta = cliente_backend.get("/api/servicios")
    assert respuesta.status_code == 200
    assert [servicio["id"] for servicio in respuesta.get_json()] == [1]
    assert "WHERE activo = TRUE" in db.consultar.call_args.args[0]


# --- alta ---
def test_crear_servicio_devuelve_201_con_el_servicio(cliente_backend, cabeceras_admin, db):
    datos = {"nombre": "  Combo familiar ", "descripcion": " Dos pochoclos ", "precio": 9500.5}
    respuesta = cliente_backend.post("/api/admin/servicios", json=datos, headers=cabeceras_admin)
    assert respuesta.status_code == 201
    assert respuesta.get_json() == {
        "id": 9, "nombre": "Combo familiar", "descripcion": "Dos pochoclos", "precio": 9500.5, "activo": True,
    }
    sql, parametros = db.ejecutar.call_args.args
    assert "INSERT INTO servicios" in sql
    assert parametros == ("Combo familiar", "Dos pochoclos", Decimal("9500.5"))


@pytest.mark.parametrize("descripcion", [None, "", "   "])
def test_crear_servicio_sin_descripcion_guarda_null(cliente_backend, cabeceras_admin, db, descripcion):
    datos = {"nombre": "Gaseosa", "descripcion": descripcion, "precio": 2500}
    respuesta = cliente_backend.post("/api/admin/servicios", json=datos, headers=cabeceras_admin)
    assert respuesta.status_code == 201
    assert respuesta.get_json()["descripcion"] is None
    assert db.ejecutar.call_args.args[1][1] is None


def test_crear_servicio_con_nombre_duplicado_devuelve_409(cliente_backend, cabeceras_admin, db):
    db.ejecutar.side_effect = duplicado()
    respuesta = cliente_backend.post("/api/admin/servicios", json=SERVICIO_NUEVO, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 409, "SERVICIO_DUPLICADO")


@pytest.mark.parametrize("precio", ["9500", None, True, False, 0, -10, 0.001, 100000000, [9500]])
def test_crear_servicio_con_precio_invalido_devuelve_400(cliente_backend, cabeceras_admin, db, precio):
    datos = {**SERVICIO_NUEVO, "precio": precio}
    respuesta = cliente_backend.post("/api/admin/servicios", json=datos, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


@pytest.mark.parametrize("cambios", [
    {"nombre": ""}, {"nombre": "   "}, {"nombre": None}, {"nombre": 5}, {"nombre": "x" * 101},
    {"descripcion": 7}, {"descripcion": "x" * 256},
])
def test_crear_servicio_con_nombre_o_descripcion_invalidos_devuelve_400(cliente_backend, cabeceras_admin, db, cambios):
    respuesta = cliente_backend.post("/api/admin/servicios", json={**SERVICIO_NUEVO, **cambios}, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


def test_crear_servicio_sin_nombre_devuelve_400(cliente_backend, cabeceras_admin, db):
    respuesta = cliente_backend.post("/api/admin/servicios", json={"precio": 100}, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")


def test_crear_servicio_con_cuerpo_que_no_es_objeto_devuelve_400(cliente_backend, cabeceras_admin, db):
    respuesta = cliente_backend.post("/api/admin/servicios", json=[1, 2], headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")


# --- modificación ---
def test_modificar_servicio_devuelve_el_servicio_y_conserva_el_estado(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila(id=4, activo=0)
    datos = {"nombre": "Gaseosa grande", "descripcion": "1 litro", "precio": 3000}
    respuesta = cliente_backend.put("/api/admin/servicios/4", json=datos, headers=cabeceras_admin)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "id": 4, "nombre": "Gaseosa grande", "descripcion": "1 litro", "precio": 3000.0, "activo": False,
    }
    sql, parametros = db.ejecutar.call_args.args
    assert sql.startswith("UPDATE servicios SET nombre = %s, descripcion = %s, precio = %s WHERE id = %s")
    assert parametros == ("Gaseosa grande", "1 litro", Decimal("3000"), 4)


def test_modificar_servicio_inexistente_devuelve_404(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = None
    respuesta = cliente_backend.put("/api/admin/servicios/99", json=SERVICIO_NUEVO, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")
    db.ejecutar.assert_not_called()


def test_modificar_servicio_con_nombre_duplicado_devuelve_409(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila()
    db.ejecutar.side_effect = duplicado()
    respuesta = cliente_backend.put("/api/admin/servicios/1", json=SERVICIO_NUEVO, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 409, "SERVICIO_DUPLICADO")


@pytest.mark.parametrize("cambios", [{"nombre": " "}, {"precio": 0}, {"precio": "abc"}])
def test_modificar_servicio_con_datos_invalidos_devuelve_400(cliente_backend, cabeceras_admin, db, cambios):
    db.consultar_uno.return_value = fila()
    respuesta = cliente_backend.put("/api/admin/servicios/1", json={**SERVICIO_NUEVO, **cambios}, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


# --- baja lógica ---
def test_baja_de_servicio_hace_update_de_activo_y_no_delete(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila()
    respuesta = cliente_backend.delete("/api/admin/servicios/1", headers=cabeceras_admin)
    assert respuesta.status_code == 204
    sql, parametros = db.ejecutar.call_args.args
    assert sql == "UPDATE servicios SET activo = FALSE WHERE id = %s"
    assert parametros == (1,)
    sentencias = [llamada.args[0] for llamada in db.ejecutar.call_args_list]
    assert not any("DELETE" in sentencia or "compra_servicios" in sentencia for sentencia in sentencias)


def test_baja_de_servicio_inexistente_devuelve_404(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = None
    respuesta = cliente_backend.delete("/api/admin/servicios/99", headers=cabeceras_admin)
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")
    db.ejecutar.assert_not_called()


def test_servicio_dado_de_baja_no_aparece_en_el_listado_publico(cliente_backend, cabeceras_admin, db):
    """La base simulada aplica el filtro de activo que pide el SQL: tras la baja, el servicio 1 ya no se lista."""
    tabla = {1: fila(id=1), 2: fila(id=2, nombre="Estacionamiento")}

    def dar_de_baja(sql, parametros):
        tabla[parametros[0]]["activo"] = 0

    def listar(sql, parametros=None):
        filas = [dict(f) for f in tabla.values()]
        return [f for f in filas if f["activo"]] if "activo = TRUE" in sql else filas

    db.consultar_uno.side_effect = lambda sql, parametros: dict(tabla[parametros[0]])
    db.ejecutar.side_effect = dar_de_baja
    db.consultar.side_effect = listar

    assert cliente_backend.delete("/api/admin/servicios/1", headers=cabeceras_admin).status_code == 204
    publicos = cliente_backend.get("/api/servicios").get_json()
    assert [servicio["id"] for servicio in publicos] == [2]
    todos = cliente_backend.get("/api/admin/servicios", headers=cabeceras_admin).get_json()
    assert {servicio["id"]: servicio["activo"] for servicio in todos} == {1: False, 2: True}
