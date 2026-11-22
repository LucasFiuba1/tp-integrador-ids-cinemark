"""Pruebas de "Olvidé mi contraseña": token firmado, endpoints, email por Mailjet y pantallas del sitio.

La base y Mailjet se simulan: ninguna prueba toca MySQL ni sale a la red.
"""
import logging
from unittest.mock import patch

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from src.backend import tokens
from src.backend.services import correo
from src.backend.services.cuentas import MENSAJE_RECUPERACION
from src.frontend.validaciones import validar_recuperar, validar_restablecer
from src.tests.utilidades import afirmar_error_json, simular_bd

HASH_ACTUAL = generate_password_hash("vieja-clave-123", method="pbkdf2:sha256")
USUARIO = {"id": 7, "nombre": "Ana Pérez", "email": "ana@mail.com", "password_hash": HASH_ACTUAL}


@pytest.fixture
def bd():
    with simular_bd(destinos=("src.backend.services.cuentas",)) as simulacion:
        yield simulacion


@pytest.fixture
def envio():
    with patch("src.backend.services.cuentas.correo.enviar_recuperacion", return_value=True) as enviar:
        yield enviar


def _token(usuario_id=7, password_hash=HASH_ACTUAL):
    return tokens.firmar_recuperacion(usuario_id, password_hash)


# --- token ---
def test_el_token_de_recuperacion_se_lee_con_el_usuario_y_la_huella(app_backend):
    assert tokens.leer_recuperacion(_token()) == (7, tokens.huella_password(HASH_ACTUAL))


def test_el_token_no_expone_el_hash_de_la_contrasena(app_backend):
    assert HASH_ACTUAL not in _token()


@pytest.mark.parametrize("token", ["", None, 123, "trucho", "a.b.c"])
def test_un_token_vacio_o_alterado_no_se_lee(app_backend, token):
    assert tokens.leer_recuperacion(token) is None


def test_los_tokens_de_qr_y_cancelacion_no_sirven_para_recuperar(app_backend):
    assert tokens.leer_recuperacion(tokens.firmar_qr(7)) is None
    assert tokens.leer_recuperacion(tokens.firmar_cancelacion(7)) is None


def test_el_token_vence_a_la_hora(app_backend):
    token = _token()
    with patch("itsdangerous.timed.time.time", return_value=10**10):
        assert tokens.leer_recuperacion(token) is None


# --- POST /api/auth/recuperar ---
def test_recuperar_con_email_registrado_envia_el_enlace(cliente_backend, bd, envio):
    bd.consultar_uno.return_value = USUARIO
    respuesta = cliente_backend.post("/api/auth/recuperar", json={"email": "  ANA@mail.com "})
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"mensaje": MENSAJE_RECUPERACION}
    assert bd.consultar_uno.call_args.args[1] == ("ana@mail.com",)
    usuario, token = envio.call_args.args
    assert usuario == USUARIO and tokens.leer_recuperacion(token)[0] == 7


def test_recuperar_con_email_no_registrado_responde_igual_y_no_envia(cliente_backend, bd, envio):
    respuesta = cliente_backend.post("/api/auth/recuperar", json={"email": "nadie@mail.com"})
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"mensaje": MENSAJE_RECUPERACION}
    envio.assert_not_called()


def test_recuperar_responde_igual_aunque_el_email_no_salga(cliente_backend, bd, envio):
    bd.consultar_uno.return_value = USUARIO
    envio.return_value = False
    assert cliente_backend.post("/api/auth/recuperar", json={"email": "ana@mail.com"}).status_code == 200


@pytest.mark.parametrize("cuerpo", [{}, {"email": "no-es-email"}, {"email": 5}])
def test_recuperar_con_email_invalido_devuelve_400(cliente_backend, bd, envio, cuerpo):
    afirmar_error_json(cliente_backend.post("/api/auth/recuperar", json=cuerpo), 400, "DATOS_INVALIDOS")
    envio.assert_not_called()


# --- GET y POST /api/auth/restablecer ---
def test_validar_un_token_vigente(cliente_backend, bd):
    bd.consultar_uno.return_value = USUARIO
    respuesta = cliente_backend.get("/api/auth/restablecer", query_string={"token": _token()})
    assert respuesta.status_code == 200 and respuesta.get_json() == {"valido": True}


def test_restablecer_guarda_el_hash_de_la_nueva_contrasena(cliente_backend, bd):
    bd.consultar_uno.return_value = USUARIO
    respuesta = cliente_backend.post("/api/auth/restablecer", json={"token": _token(), "password": "nueva-clave-456"})
    assert respuesta.status_code == 200
    sql, (password_hash, usuario_id) = bd.ejecutar.call_args.args
    assert sql.startswith("UPDATE usuarios SET password_hash = %s")
    assert usuario_id == 7 and check_password_hash(password_hash, "nueva-clave-456")


def test_un_enlace_ya_usado_no_sirve_otra_vez(cliente_backend, bd):
    """Después de cambiar la contraseña el hash es otro: la huella del token deja de coincidir."""
    bd.consultar_uno.return_value = {**USUARIO, "password_hash": generate_password_hash("otra-clave-789", method="pbkdf2:sha256")}
    respuesta = cliente_backend.post("/api/auth/restablecer", json={"token": _token(), "password": "nueva-clave-456"})
    afirmar_error_json(respuesta, 400, "TOKEN_INVALIDO")
    bd.ejecutar.assert_not_called()


@pytest.mark.parametrize("token", ["", "trucho", None])
def test_restablecer_con_token_invalido_devuelve_400(cliente_backend, bd, token):
    respuesta = cliente_backend.post("/api/auth/restablecer", json={"token": token, "password": "nueva-clave-456"})
    afirmar_error_json(respuesta, 400, "TOKEN_INVALIDO")
    bd.consultar_uno.assert_not_called()


def test_restablecer_de_un_usuario_que_ya_no_existe_devuelve_400(cliente_backend, bd):
    respuesta = cliente_backend.get("/api/auth/restablecer", query_string={"token": _token()})
    afirmar_error_json(respuesta, 400, "TOKEN_INVALIDO")


@pytest.mark.parametrize("password", ["corta", "x" * 129, 12345678, None])
def test_restablecer_con_contrasena_invalida_devuelve_400(cliente_backend, bd, password):
    bd.consultar_uno.return_value = USUARIO
    respuesta = cliente_backend.post("/api/auth/restablecer", json={"token": _token(), "password": password})
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    bd.ejecutar.assert_not_called()


# --- email por Mailjet ---
@pytest.fixture
def mailjet(app_backend):
    app_backend.config.update(
        MAILJET_API_KEY="clave", MAILJET_SECRET_KEY="secreto", FRONTEND_URL="https://cine.test",
    )
    respuesta = {"Messages": [{"Status": "success", "To": [{"Email": "ana@mail.com", "MessageID": 1}]}]}
    with patch("src.backend.services.correo.requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = respuesta
        yield post


def test_el_email_de_recuperacion_lleva_el_enlace_al_sitio_sin_qr(mailjet):
    assert correo.enviar_recuperacion(USUARIO, "token-firmado") is True
    [mensaje] = mailjet.call_args.kwargs["json"]["Messages"]
    assert mensaje["To"] == [{"Email": "ana@mail.com", "Name": "Ana Pérez"}]
    assert mensaje["Subject"] == "Restablecé tu contraseña de Cine Paradiso"
    for parte in (mensaje["HTMLPart"], mensaje["TextPart"]):
        assert "https://cine.test/restablecer/token-firmado" in parte
        assert "60 minutos" in parte
    assert "InlinedAttachments" not in mensaje
    assert "Película" not in mensaje["HTMLPart"]


def test_el_log_de_un_fallo_de_recuperacion_no_filtra_email_ni_token(mailjet, caplog):
    mailjet.return_value.status_code = 401
    with caplog.at_level(logging.DEBUG):
        assert correo.enviar_recuperacion(USUARIO, "token-firmado") is False
    assert "usuario 7" in caplog.text
    assert "ana@mail.com" not in caplog.text and "token-firmado" not in caplog.text


# --- validaciones del frontend ---
def test_validar_recuperar_exige_un_email():
    assert validar_recuperar({"email": ""}) == {"email": "Ingresá tu email."}
    assert validar_recuperar({"email": "ana@mail.com"}) == {}


def test_validar_restablecer_exige_largo_y_que_coincidan():
    assert set(validar_restablecer({"password": "corta", "repetir_password": "otra"})) == {
        "password", "repetir_password",
    }
    assert validar_restablecer({"password": "secreta123", "repetir_password": "secreta123"}) == {}


# --- pantallas del sitio ---
@pytest.fixture
def llamar():
    with patch("src.frontend.routes.publico.llamar") as llamar:
        yield llamar


def _error(status, codigo, mensaje):
    return {"status": status, "codigo": codigo, "mensaje": mensaje}


def test_ingresar_tiene_el_enlace_olvide_mi_contrasena(cliente_frontend):
    assert 'href="/olvide-contrasena"' in cliente_frontend.get("/ingresar").get_data(as_text=True)


def test_olvide_muestra_el_formulario_de_email(cliente_frontend):
    html = cliente_frontend.get("/olvide-contrasena").get_data(as_text=True)
    assert "¿Olvidaste tu contraseña?" in html
    assert '<form method="post" action="/olvide-contrasena"' in html and 'name="email"' in html


def test_olvide_con_email_invalido_no_llama_al_backend(cliente_frontend, llamar):
    respuesta = cliente_frontend.post("/olvide-contrasena", data={"email": "4r"})
    assert respuesta.status_code == 400
    llamar.assert_not_called()


def test_olvide_envia_el_email_y_vuelve_al_login_con_el_aviso(cliente_frontend, llamar):
    llamar.return_value = ({"mensaje": MENSAJE_RECUPERACION}, None)
    respuesta = cliente_frontend.post("/olvide-contrasena", data={"email": " ana@mail.com "}, follow_redirects=True)
    assert respuesta.request.path == "/ingresar"
    assert MENSAJE_RECUPERACION in respuesta.get_data(as_text=True)
    llamar.assert_any_call("POST", "/api/auth/recuperar", json={"email": "ana@mail.com"})


def test_olvide_muestra_el_error_si_el_backend_no_responde(cliente_frontend, llamar):
    llamar.return_value = (None, _error(503, "BACKEND_NO_DISPONIBLE", "El servicio no está disponible."))
    respuesta = cliente_frontend.post("/olvide-contrasena", data={"email": "ana@mail.com"})
    assert respuesta.status_code == 503
    assert "El servicio no está disponible." in respuesta.get_data(as_text=True)


def test_restablecer_con_enlace_vigente_muestra_el_formulario(cliente_frontend, llamar):
    llamar.return_value = ({"valido": True}, None)
    html = cliente_frontend.get("/restablecer/tok123").get_data(as_text=True)
    assert '<form method="post" action="/restablecer/tok123"' in html
    assert 'name="password"' in html and 'name="repetir_password"' in html
    llamar.assert_any_call("GET", "/api/auth/restablecer", params={"token": "tok123"})


def test_restablecer_con_enlace_vencido_ofrece_pedir_otro(cliente_frontend, llamar):
    llamar.return_value = (None, _error(400, "TOKEN_INVALIDO", "El enlace no es válido o venció."))
    respuesta = cliente_frontend.get("/restablecer/tok123")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert "El enlace no es válido o venció." in html and 'href="/olvide-contrasena"' in html
    assert 'name="password"' not in html


def test_restablecer_con_contrasenas_distintas_no_llama_al_backend(cliente_frontend, llamar):
    respuesta = cliente_frontend.post(
        "/restablecer/tok123", data={"password": "secreta123", "repetir_password": "otra12345"}
    )
    assert respuesta.status_code == 400
    assert "Las contraseñas no coinciden." in respuesta.get_data(as_text=True)
    llamar.assert_not_called()


def test_restablecer_guarda_y_vuelve_al_login(cliente_frontend, llamar):
    llamar.return_value = ({"mensaje": "Listo, ya podés ingresar con tu nueva contraseña."}, None)
    respuesta = cliente_frontend.post(
        "/restablecer/tok123", data={"password": "secreta123", "repetir_password": "secreta123"},
        follow_redirects=True,
    )
    assert respuesta.request.path == "/ingresar"
    assert "Listo, ya podés ingresar con tu nueva contraseña." in respuesta.get_data(as_text=True)
    llamar.assert_any_call("POST", "/api/auth/restablecer", json={"token": "tok123", "password": "secreta123"})


def test_restablecer_con_enlace_ya_usado_muestra_el_error(cliente_frontend, llamar):
    llamar.return_value = (None, _error(400, "TOKEN_INVALIDO", "El enlace no es válido o venció."))
    respuesta = cliente_frontend.post(
        "/restablecer/tok123", data={"password": "secreta123", "repetir_password": "secreta123"}
    )
    assert respuesta.status_code == 400
    assert "El enlace no es válido o venció." in respuesta.get_data(as_text=True)
