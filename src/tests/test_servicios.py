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


# --- bordes: precio (JSON con NaN/Infinity literales, límites de DECIMAL(10, 2)) ---
@pytest.mark.parametrize("precio_crudo", [
    "NaN", "Infinity", "-Infinity", "1e400", "-0", "-0.0", "0.0", "1e-7", "0.009", "99999999.991", "100000000.0",
    "1" + "0" * 400, "{}", '"NaN"',
])
def test_crear_servicio_con_precio_crudo_invalido_devuelve_400(cliente_backend, cabeceras_admin, db, precio_crudo):
    """Se arma el JSON a mano: Flask acepta NaN e Infinity literales y los convierte en float."""
    cuerpo = '{"nombre": "Gaseosa", "precio": ' + precio_crudo + "}"
    respuesta = cliente_backend.post(
        "/api/admin/servicios", data=cuerpo, content_type="application/json", headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


@pytest.mark.parametrize("precio_crudo, esperado", [
    ("0.01", Decimal("0.01")), ("99999999.99", Decimal("99999999.99")), ("99999999", Decimal("99999999")),
    ("1e2", Decimal("100.0")), ("0.1", Decimal("0.1")), ("19.99", Decimal("19.99")),
])
def test_crear_servicio_con_precio_en_el_limite_valido_devuelve_201(
    cliente_backend, cabeceras_admin, db, precio_crudo, esperado
):
    cuerpo = '{"nombre": "Gaseosa", "precio": ' + precio_crudo + "}"
    respuesta = cliente_backend.post(
        "/api/admin/servicios", data=cuerpo, content_type="application/json", headers=cabeceras_admin
    )
    assert respuesta.status_code == 201
    assert db.ejecutar.call_args.args[1][2] == esperado
    assert respuesta.get_json()["precio"] == float(esperado)


@pytest.mark.parametrize("precio_crudo", ["NaN", "Infinity", "-1", "0.001"])
def test_modificar_servicio_con_precio_crudo_invalido_devuelve_400(cliente_backend, cabeceras_admin, db, precio_crudo):
    db.consultar_uno.return_value = fila()
    cuerpo = '{"nombre": "Gaseosa", "precio": ' + precio_crudo + "}"
    respuesta = cliente_backend.put(
        "/api/admin/servicios/1", data=cuerpo, content_type="application/json", headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


# --- bordes: precio_valido directo (lo comparten servicios y funciones) ---
@pytest.mark.parametrize("valor", [
    Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-0.01"), Decimal("0.00"), Decimal("1.234"),
    float("nan"), float("inf"), -float("inf"), True, None, "10", b"10", [10], {"monto": 10},
])
def test_precio_valido_con_valor_invalido_corta_con_400(app_backend, valor):
    from werkzeug.exceptions import HTTPException

    from src.backend.services.validaciones import precio_valido

    with pytest.raises(HTTPException) as corte:
        precio_valido(valor)
    afirmar_error_json(corte.value.response, 400, "DATOS_INVALIDOS")


@pytest.mark.parametrize("valor, esperado", [
    (0.1, Decimal("0.1")), (19.99, Decimal("19.99")), (Decimal("7000.50"), Decimal("7000.50")), (1, Decimal("1")),
])
def test_precio_valido_devuelve_el_decimal_exacto_sin_ruido_binario(app_backend, valor, esperado):
    from src.backend.services.validaciones import precio_valido

    resultado = precio_valido(valor)
    assert type(resultado) is Decimal
    assert resultado == esperado
    assert str(resultado) == str(esperado)


def test_funciones_y_servicios_usan_la_misma_validacion_de_precio():
    from src.backend.services import funciones, servicios, validaciones

    assert funciones.precio_valido is validaciones.precio_valido
    assert servicios.precio_valido is validaciones.precio_valido


# --- bordes: cuerpo del request ---
@pytest.mark.parametrize("cuerpo, tipo", [
    ("null", "application/json"), ('"Gaseosa"', "application/json"), ("42", "application/json"),
    ("", "application/json"), ("{", "application/json"), ('{"nombre": "Gaseosa", "precio": 10,}', "application/json"),
    ('{"nombre": "Gaseosa", "precio": 10}', "text/plain"),
    ("nombre=Gaseosa&precio=10", "application/x-www-form-urlencoded"),
])
def test_crear_servicio_con_cuerpo_que_no_es_objeto_json_devuelve_400(
    cliente_backend, cabeceras_admin, db, cuerpo, tipo
):
    respuesta = cliente_backend.post("/api/admin/servicios", data=cuerpo, content_type=tipo, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


@pytest.mark.parametrize("cuerpo", ["null", "[1, 2]", '"Gaseosa"', ""])
def test_modificar_servicio_existente_con_cuerpo_que_no_es_objeto_devuelve_400(
    cliente_backend, cabeceras_admin, db, cuerpo
):
    db.consultar_uno.return_value = fila()
    respuesta = cliente_backend.put(
        "/api/admin/servicios/1", data=cuerpo, content_type="application/json", headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


def test_modificar_servicio_es_reemplazo_completo_y_sin_nombre_devuelve_400(cliente_backend, cabeceras_admin, db):
    """El PUT reemplaza: un cuerpo parcial no conserva el nombre anterior."""
    db.consultar_uno.return_value = fila()
    respuesta = cliente_backend.put("/api/admin/servicios/1", json={"precio": 3000}, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


def test_modificar_servicio_ignora_activo_del_cuerpo(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila(activo=0)
    datos = {**SERVICIO_NUEVO, "activo": True, "id": 77}
    respuesta = cliente_backend.put("/api/admin/servicios/1", json=datos, headers=cabeceras_admin)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["activo"] is False
    assert respuesta.get_json()["id"] == 1
    sql, parametros = db.ejecutar.call_args.args
    assert "activo" not in sql
    assert parametros[-1] == 1


def test_crear_servicio_ignora_id_y_activo_del_cuerpo(cliente_backend, cabeceras_admin, db):
    datos = {**SERVICIO_NUEVO, "id": 777, "activo": False}
    respuesta = cliente_backend.post("/api/admin/servicios", json=datos, headers=cabeceras_admin)
    assert respuesta.status_code == 201
    assert respuesta.get_json()["id"] == 9
    assert respuesta.get_json()["activo"] is True
    assert len(db.ejecutar.call_args.args[1]) == 3


# --- bordes: nombre y descripción ---
@pytest.mark.parametrize("nombre_crudo, guardado", [
    ("\t Café ☕ \n", "Café ☕"), (" Pochoclos ", "Pochoclos"), (" " + "ñ" * 100 + " ", "ñ" * 100),
    ("x" * 100, "x" * 100),
])
def test_crear_servicio_guarda_el_nombre_sin_espacios_en_los_extremos(
    cliente_backend, cabeceras_admin, db, nombre_crudo, guardado
):
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json={**SERVICIO_NUEVO, "nombre": nombre_crudo}, headers=cabeceras_admin
    )
    assert respuesta.status_code == 201
    assert respuesta.get_json()["nombre"] == guardado
    assert db.ejecutar.call_args.args[1][0] == guardado


@pytest.mark.parametrize("nombre", ["\t\n", "  ", True, [], ["Gaseosa"], {"es": "Gaseosa"}, "ñ" * 101])
def test_crear_servicio_con_nombre_en_blanco_o_de_otro_tipo_devuelve_400(cliente_backend, cabeceras_admin, db, nombre):
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json={**SERVICIO_NUEVO, "nombre": nombre}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


def test_modificar_servicio_guarda_el_nombre_sin_espacios(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila()
    datos = {**SERVICIO_NUEVO, "nombre": "  Gaseosa grande\t"}
    respuesta = cliente_backend.put("/api/admin/servicios/1", json=datos, headers=cabeceras_admin)
    assert respuesta.status_code == 200
    assert db.ejecutar.call_args.args[1][0] == "Gaseosa grande"


@pytest.mark.parametrize("descripcion, guardada", [("d" * 255, "d" * 255), ("  " + "d" * 255 + "  ", "d" * 255)])
def test_crear_servicio_con_descripcion_en_el_limite_devuelve_201(
    cliente_backend, cabeceras_admin, db, descripcion, guardada
):
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json={**SERVICIO_NUEVO, "descripcion": descripcion}, headers=cabeceras_admin
    )
    assert respuesta.status_code == 201
    assert db.ejecutar.call_args.args[1][1] == guardada


@pytest.mark.parametrize("descripcion", [True, ["texto"], {"a": 1}, 0])
def test_crear_servicio_con_descripcion_de_otro_tipo_devuelve_400(cliente_backend, cabeceras_admin, db, descripcion):
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json={**SERVICIO_NUEVO, "descripcion": descripcion}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    db.ejecutar.assert_not_called()


def test_crear_servicio_con_inyeccion_sql_en_el_nombre_lo_pasa_como_parametro(cliente_backend, cabeceras_admin, db):
    nombre = "x'); DROP TABLE servicios; --"
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json={**SERVICIO_NUEVO, "nombre": nombre}, headers=cabeceras_admin
    )
    assert respuesta.status_code == 201
    sql, parametros = db.ejecutar.call_args.args
    assert "DROP" not in sql
    assert parametros[0] == nombre


# --- bordes: duplicados ---
def test_crear_dos_veces_el_mismo_servicio_el_segundo_devuelve_409(cliente_backend, cabeceras_admin, db):
    db.ejecutar.side_effect = [9, duplicado()]
    primera = cliente_backend.post("/api/admin/servicios", json=SERVICIO_NUEVO, headers=cabeceras_admin)
    segunda = cliente_backend.post("/api/admin/servicios", json=SERVICIO_NUEVO, headers=cabeceras_admin)
    assert primera.status_code == 201
    afirmar_error_json(segunda, 409, "SERVICIO_DUPLICADO")


def test_renombrar_servicio_inactivo_a_un_nombre_existente_devuelve_409(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila(id=4, activo=0)
    db.ejecutar.side_effect = duplicado()
    datos = {"nombre": "Gaseosa", "precio": 2500}
    respuesta = cliente_backend.put("/api/admin/servicios/4", json=datos, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 409, "SERVICIO_DUPLICADO")


# --- bordes: ids en la URL ---
@pytest.mark.parametrize("metodo", ["PUT", "DELETE"])
def test_servicio_con_id_cero_devuelve_404(cliente_backend, cabeceras_admin, db, metodo):
    db.consultar_uno.return_value = None
    respuesta = cliente_backend.open(
        "/api/admin/servicios/0", method=metodo, json=SERVICIO_NUEVO, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")
    db.ejecutar.assert_not_called()


@pytest.mark.parametrize("metodo", ["PUT", "DELETE"])
@pytest.mark.parametrize("id_crudo", ["-1", "abc", "1.5", "%20"])
def test_servicio_con_id_no_entero_positivo_devuelve_404_json(cliente_backend, cabeceras_admin, db, metodo, id_crudo):
    respuesta = cliente_backend.open(
        "/api/admin/servicios/" + id_crudo, method=metodo, json=SERVICIO_NUEVO, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")
    db.consultar_uno.assert_not_called()
    db.ejecutar.assert_not_called()


@pytest.mark.parametrize("metodo, ruta", [
    ("PATCH", "/api/admin/servicios/1"), ("POST", "/api/admin/servicios/1"),
    ("DELETE", "/api/admin/servicios"), ("POST", "/api/servicios"), ("DELETE", "/api/servicios"),
])
def test_metodo_no_permitido_devuelve_405_json(cliente_backend, cabeceras_admin, db, metodo, ruta):
    respuesta = cliente_backend.open(ruta, method=metodo, json=SERVICIO_NUEVO, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 405, "METODO_NO_PERMITIDO")
    db.ejecutar.assert_not_called()


# --- bordes: baja ---
def test_baja_de_servicio_ya_inactivo_es_idempotente_y_devuelve_204(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila(activo=0)
    respuesta = cliente_backend.delete("/api/admin/servicios/1", headers=cabeceras_admin)
    assert respuesta.status_code == 204
    assert respuesta.data == b""
    sentencias = [llamada.args[0] for llamada in db.ejecutar.call_args_list]
    assert sentencias == ["UPDATE servicios SET activo = FALSE WHERE id = %s"]


def test_baja_dos_veces_seguidas_nunca_ejecuta_delete(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.side_effect = [fila(), fila(activo=0)]
    primera = cliente_backend.delete("/api/admin/servicios/1", headers=cabeceras_admin)
    segunda = cliente_backend.delete("/api/admin/servicios/1", headers=cabeceras_admin)
    assert (primera.status_code, segunda.status_code) == (204, 204)
    assert all("DELETE" not in llamada.args[0] for llamada in db.ejecutar.call_args_list)


def test_baja_ignora_el_cuerpo_del_request(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila()
    respuesta = cliente_backend.delete("/api/admin/servicios/1", data="no es json", headers=cabeceras_admin)
    assert respuesta.status_code == 204
    assert db.ejecutar.call_args.args[1] == (1,)


# --- bordes: seguridad y formato de error ---
@pytest.mark.parametrize("metodo, ruta", RUTAS_ADMIN)
def test_rutas_admin_sin_token_devuelven_error_json_no_autenticado(cliente_backend, db, metodo, ruta):
    respuesta = cliente_backend.open(ruta, method=metodo, json=SERVICIO_NUEVO)
    afirmar_error_json(respuesta, 401, "NO_AUTENTICADO")


@pytest.mark.parametrize("cabecera", ["Bearer ", "Bearer token-falso", "Bearer a.b.c"])
@pytest.mark.parametrize("metodo, ruta", RUTAS_ADMIN)
def test_rutas_admin_con_token_invalido_devuelven_401(cliente_backend, usuarios, db, metodo, ruta, cabecera):
    respuesta = cliente_backend.open(ruta, method=metodo, json=SERVICIO_NUEVO, headers={"Authorization": cabecera})
    afirmar_error_json(respuesta, 401, "TOKEN_INVALIDO")
    db.ejecutar.assert_not_called()
    db.consultar.assert_not_called()


@pytest.mark.parametrize("cabecera", ["Basic YWRtaW46YWRtaW4=", "bearer token", "Token abc"])
def test_rutas_admin_con_esquema_de_autorizacion_distinto_devuelven_401(cliente_backend, usuarios, db, cabecera):
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json=SERVICIO_NUEVO, headers={"Authorization": cabecera}
    )
    afirmar_error_json(respuesta, 401, "NO_AUTENTICADO")
    db.ejecutar.assert_not_called()


def test_rutas_admin_con_token_de_usuario_inexistente_devuelven_401(cliente_backend, usuarios, db):
    from src.tests.utilidades import cabeceras_de

    respuesta = cliente_backend.post(
        "/api/admin/servicios", json=SERVICIO_NUEVO, headers=cabeceras_de({"id": 999})
    )
    afirmar_error_json(respuesta, 401, "TOKEN_INVALIDO")
    db.ejecutar.assert_not_called()


def test_listar_publico_con_token_invalido_igual_responde_200(cliente_backend, db):
    db.consultar.return_value = []
    respuesta = cliente_backend.get("/api/servicios", headers={"Authorization": "Bearer basura"})
    assert respuesta.status_code == 200
    assert respuesta.get_json() == []


def test_listar_publico_vacio_devuelve_lista_vacia(cliente_backend, db):
    db.consultar.return_value = []
    respuesta = cliente_backend.get("/api/servicios")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == []


def test_listar_publico_ordena_por_nombre_y_nunca_pide_inactivos(cliente_backend, db):
    db.consultar.return_value = []
    cliente_backend.get("/api/servicios")
    sql = db.consultar.call_args.args[0]
    assert "WHERE activo = TRUE" in sql
    assert sql.rstrip().endswith("ORDER BY nombre")


# --- fallas de la base ---
@pytest.mark.parametrize("metodo, ruta, operacion", [
    ("GET", "/api/servicios", "consultar"),
    ("GET", "/api/admin/servicios", "consultar"),
    ("POST", "/api/admin/servicios", "ejecutar"),
    ("PUT", "/api/admin/servicios/1", "consultar_uno"),
    ("DELETE", "/api/admin/servicios/1", "consultar_uno"),
])
def test_caida_de_la_base_devuelve_500_en_formato_json(cliente_backend, cabeceras_admin, db, metodo, ruta, operacion):
    getattr(db, operacion).side_effect = pymysql.err.OperationalError(2003, "Can't connect to MySQL server")
    respuesta = cliente_backend.open(ruta, method=metodo, json=SERVICIO_NUEVO, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 500, "ERROR_INTERNO")
    assert "MySQL" not in respuesta.get_json()["error"]["mensaje"]


def test_caida_de_la_base_en_el_update_de_la_baja_devuelve_500_json(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila()
    db.ejecutar.side_effect = pymysql.err.OperationalError(2013, "Lost connection")
    respuesta = cliente_backend.delete("/api/admin/servicios/1", headers=cabeceras_admin)
    afirmar_error_json(respuesta, 500, "ERROR_INTERNO")


def test_error_de_integridad_en_put_devuelve_409_sin_filtrar_el_detalle_de_mysql(cliente_backend, cabeceras_admin, db):
    """Cualquier IntegrityError del UPDATE se informa como 409, nunca como 500 con traza."""
    db.consultar_uno.return_value = fila()
    db.ejecutar.side_effect = pymysql.err.IntegrityError(1062, "Duplicate entry 'Gaseosa' for key 'nombre'")
    respuesta = cliente_backend.put("/api/admin/servicios/1", json=SERVICIO_NUEVO, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 409, "SERVICIO_DUPLICADO")
    assert "Duplicate" not in respuesta.get_json()["error"]["mensaje"]


# --- reactivación ---
def test_reactivar_servicio_devuelve_204_y_actualiza_estado(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = fila(activo=0)
    respuesta = cliente_backend.post("/api/admin/servicios/1/reactivar", headers=cabeceras_admin)
    assert respuesta.status_code == 204
    sql, parametros = db.ejecutar.call_args.args
    assert sql == "UPDATE servicios SET activo = TRUE WHERE id = %s"
    assert parametros == (1,)

def test_reactivar_servicio_inexistente_devuelve_404(cliente_backend, cabeceras_admin, db):
    db.consultar_uno.return_value = None
    respuesta = cliente_backend.post("/api/admin/servicios/99/reactivar", headers=cabeceras_admin)
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")
    db.ejecutar.assert_not_called()

def test_reactivar_servicio_sin_permisos(cliente_backend, cabeceras_cliente, db):
    respuesta = cliente_backend.post("/api/admin/servicios/1/reactivar", headers=cabeceras_cliente)
    afirmar_error_json(respuesta, 403, "SIN_PERMISO")
    db.ejecutar.assert_not_called()
