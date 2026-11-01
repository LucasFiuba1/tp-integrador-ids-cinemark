"""Pruebas de los endpoints de registro e inicio de sesión (SCRUM-45) con la base simulada."""
from unittest.mock import patch

import pymysql
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from src.backend.auth import _serializador

REGISTRO = {"nombre": "Ana Pérez", "email": "ana@mail.com", "password": "secreta123"}
USUARIO = {"id": 7, "nombre": "Ana Pérez", "rol": "cliente",
           "password_hash": generate_password_hash("secreta123", method="pbkdf2:sha256")}


@pytest.fixture
def ejecutar():
    with patch("src.backend.services.cuentas.ejecutar", return_value=7) as ejecutar:
        yield ejecutar


@pytest.fixture
def consultar_uno():
    with patch("src.backend.services.cuentas.consultar_uno", return_value=USUARIO) as consultar_uno:
        yield consultar_uno


# --- registro ---
def test_registro_crea_un_cliente_con_la_contrasena_hasheada(cliente_backend, ejecutar):
    respuesta = cliente_backend.post("/api/auth/registro", json=dict(REGISTRO, email="  Ana@Mail.com "))
    assert respuesta.status_code == 201
    assert respuesta.get_json() == {"id": 7, "nombre": "Ana Pérez", "email": "ana@mail.com", "rol": "cliente"}
    sql, (nombre, email, password_hash) = ejecutar.call_args.args
    assert "INSERT INTO usuarios" in sql and "'cliente'" in sql
    assert (nombre, email) == ("Ana Pérez", "ana@mail.com")
    assert password_hash.startswith("pbkdf2:sha256")
    assert check_password_hash(password_hash, "secreta123")


def test_registro_ignora_el_rol_enviado(cliente_backend, ejecutar):
    respuesta = cliente_backend.post("/api/auth/registro", json=dict(REGISTRO, rol="admin"))
    assert respuesta.get_json()["rol"] == "cliente"
    assert len(ejecutar.call_args.args[1]) == 3


def test_registro_con_email_repetido_devuelve_409(cliente_backend, ejecutar):
    ejecutar.side_effect = pymysql.err.IntegrityError(1062, "Duplicate entry")
    respuesta = cliente_backend.post("/api/auth/registro", json=REGISTRO)
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "EMAIL_REGISTRADO"


@pytest.mark.parametrize("cambios", [
    {"nombre": ""}, {"nombre": "   "}, {"nombre": "a" * 101}, {"nombre": 5},
    {"email": "ana"}, {"email": "ana@mail"}, {"email": None}, {"email": "a@" + "m" * 150 + ".com"},
    {"password": "corta"}, {"password": 12345678}, {"password": "x" * 129},
])
def test_registro_con_datos_invalidos_devuelve_400(cliente_backend, ejecutar, cambios):
    respuesta = cliente_backend.post("/api/auth/registro", json=dict(REGISTRO, **cambios))
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    ejecutar.assert_not_called()


@pytest.mark.parametrize("ruta", ["/api/auth/registro", "/api/auth/login"])
def test_cuerpo_que_no_es_objeto_devuelve_400(cliente_backend, ruta):
    respuesta = cliente_backend.post(ruta, json=["no", "es", "objeto"])
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"


# --- login ---
def test_login_devuelve_token_rol_y_nombre(cliente_backend, consultar_uno):
    respuesta = cliente_backend.post("/api/auth/login", json={"email": " ANA@mail.com", "password": "secreta123"})
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert (datos["rol"], datos["nombre"]) == ("cliente", "Ana Pérez")
    assert _serializador().loads(datos["token"]) == {"user_id": 7}
    assert consultar_uno.call_args.args[1] == ("ana@mail.com",)
    assert "password_hash" not in datos


def test_token_del_login_sirve_para_endpoints_protegidos(cliente_backend, consultar_uno):
    token = cliente_backend.post("/api/auth/login", json={"email": "ana@mail.com", "password": "secreta123"}) \
        .get_json()["token"]
    with patch("src.backend.auth.consultar_uno", return_value=USUARIO), \
            patch("src.backend.services.perfil.consultar", return_value=[]):
        respuesta = cliente_backend.get("/api/me/compras", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200


@pytest.mark.parametrize("usuario, password", [(USUARIO, "otra-clave"), (None, "secreta123")])
def test_login_con_credenciales_incorrectas_devuelve_401_con_el_mismo_mensaje(
        cliente_backend, consultar_uno, usuario, password):
    consultar_uno.return_value = usuario
    respuesta = cliente_backend.post("/api/auth/login", json={"email": "ana@mail.com", "password": password})
    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"] == {
        "codigo": "CREDENCIALES_INVALIDAS", "mensaje": "El email o la contraseña son incorrectos.",
    }


@pytest.mark.parametrize("cuerpo", [{}, {"email": "ana@mail.com"}, {"email": "", "password": "x"},
                                    {"email": 1, "password": "x"}, {"email": "ana@mail.com", "password": None}])
def test_login_sin_datos_devuelve_400(cliente_backend, consultar_uno, cuerpo):
    respuesta = cliente_backend.post("/api/auth/login", json=cuerpo)
    assert respuesta.status_code == 400
    consultar_uno.assert_not_called()
