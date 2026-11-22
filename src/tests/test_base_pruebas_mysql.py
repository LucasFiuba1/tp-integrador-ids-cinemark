"""Ejemplo de pruebas contra la base MySQL de pruebas: salud, login y fixtures (SCRUM-78).

Corren solo con `.env.test` (ver `.env.test.example`); sin él se saltean.
"""
from src.tests import mysql_pruebas as base_pruebas
from src.tests.mysql_pruebas import con_token


def test_salud_responde_con_la_app_de_pruebas(cliente_http):
    assert cliente_http.get("/api/salud").get_json() == {"estado": "ok"}


def test_la_app_apunta_a_la_base_de_pruebas_y_no_a_la_de_desarrollo(app_mysql, mysql_pruebas):
    assert app_mysql.config["DB_NAME"] == mysql_pruebas["DB_NAME"]
    assert app_mysql.config["DB_NAME"].endswith("_test")


def test_la_base_tiene_los_datos_del_seed(mysql_pruebas):
    conexion = base_pruebas.conectar(mysql_pruebas)
    try:
        locales = base_pruebas.filas(conexion, "SELECT COUNT(*) AS n FROM locales")[0]["n"]
        usuarios = base_pruebas.filas(conexion, "SELECT email FROM usuarios ORDER BY id LIMIT 3")
    finally:
        conexion.close()
    assert locales == 3
    assert [fila["email"] for fila in usuarios] == ["admin@cineparadiso.com", "ana@mail.com", "juan@mail.com"]


def test_login_del_admin_del_seed_da_un_token_con_rol_admin(cliente_http, token_admin):
    respuesta = cliente_http.get("/api/auth/me", headers=con_token(token_admin))
    assert respuesta.status_code == 200
    assert respuesta.get_json()["rol"] == "admin"


def test_login_del_cliente_no_entra_al_backoffice(cliente_http, token_cliente):
    respuesta = cliente_http.get("/api/admin/locales", headers=con_token(token_cliente))
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_login_con_clave_incorrecta_devuelve_401(cliente_http):
    respuesta = cliente_http.post("/api/auth/login", json={"email": "ana@mail.com", "password": "otra-clave"})
    assert respuesta.status_code == 401


def test_funcion_con_butacas_aparece_libre_en_el_mapa(cliente_http, funcion_con_butacas):
    mapa = cliente_http.get(f"/api/funciones/{funcion_con_butacas['id']}/butacas").get_json()
    estados = {butaca["id"]: butaca["estado"] for butaca in mapa["butacas"]}
    assert [estados[butaca_id] for butaca_id in funcion_con_butacas["butaca_ids"]] == ["libre"] * 4

