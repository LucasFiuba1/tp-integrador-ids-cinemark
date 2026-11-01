"""Pruebas de las pantallas de ingresar, crear cuenta y cerrar sesión (SCRUM-88, SCRUM-46)."""
from unittest.mock import patch

import pytest
import requests

from src.frontend.validaciones import leer_formulario, validar_login, validar_registro

REGISTRO_VALIDO = {"nombre": "Ana Pérez", "email": "ana@mail.com", "password": "secreta123",
                   "repetir_password": "secreta123"}
EMAIL_INVALIDO = "Ingresá un email válido, por ejemplo nombre@mail.com."


@pytest.fixture
def llamar():
    with patch("src.frontend.routes.publico.llamar") as llamar:
        yield llamar


def error_backend(status, codigo, mensaje):
    return {"status": status, "codigo": codigo, "mensaje": mensaje}


# --- pantallas ---
def test_ingresar_muestra_el_formulario_con_la_pestana_activa(cliente_frontend):
    respuesta = cliente_frontend.get("/ingresar")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "¡Hola de nuevo!" in html
    assert '<form method="post" action="/ingresar"' in html
    assert 'href="/ingresar" aria-current="page"' in html
    assert 'name="email" value="" placeholder="tu@email.com" autocomplete="email" required' in html
    assert 'type="password" name="password"' in html


def test_registro_muestra_los_cuatro_campos(cliente_frontend):
    respuesta = cliente_frontend.get("/registro")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Creá tu cuenta" in html
    assert 'href="/registro" aria-current="page"' in html
    for nombre in ("nombre", "email", "password", "repetir_password"):
        assert f'name="{nombre}"' in html
    assert html.count('minlength="8"') == 2


@pytest.mark.parametrize("ruta", ["/ingresar", "/registro"])
def test_formularios_desactivan_la_validacion_del_navegador(cliente_frontend, ruta):
    assert 'class="auth-formulario" novalidate>' in cliente_frontend.get(ruta).get_data(as_text=True)


def test_ingresar_con_email_invalido_muestra_el_error_en_el_campo(cliente_frontend):
    respuesta = cliente_frontend.post("/ingresar", data={"email": "4r", "password": "secreta123"})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert '<label class="campo campo-invalido">' in html
    assert 'value="4r"' in html
    assert 'aria-invalid="true" aria-describedby="error-email"' in html
    assert f'id="error-email">{EMAIL_INVALIDO}</small>' in html
    assert "Revisá los datos marcados" in html
    assert "secreta123" not in html


def test_registro_con_errores_conserva_nombre_y_email(cliente_frontend):
    datos = dict(REGISTRO_VALIDO, password="corta", repetir_password="otra")
    html = cliente_frontend.post("/registro", data=datos).get_data(as_text=True)
    assert 'value="Ana Pérez"' in html
    assert 'value="ana@mail.com"' in html
    assert "al menos 8 caracteres" in html
    assert "Las contraseñas no coinciden." in html
    assert 'value="corta"' not in html


# --- envío al backend (SCRUM-46) ---
def test_ingresar_como_cliente_guarda_la_sesion_y_va_a_la_cartelera(cliente_frontend, llamar):
    llamar.return_value = ({"token": "t0k3n", "rol": "cliente", "nombre": "Ana"}, None)
    respuesta = cliente_frontend.post("/ingresar", data={"email": " ana@mail.com", "password": "secreta123"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    llamar.assert_called_once_with("POST", "/api/auth/login",
                                   json={"email": "ana@mail.com", "password": "secreta123"})
    with cliente_frontend.session_transaction() as sesion:
        assert dict(sesion) == {"token": "t0k3n", "rol": "cliente", "nombre": "Ana",
                                "_flashes": [("exito", "¡Hola, Ana!")]}


def test_ingresar_como_admin_va_al_backoffice(cliente_frontend, llamar):
    llamar.return_value = ({"token": "t0k3n", "rol": "admin", "nombre": "Admin"}, None)
    respuesta = cliente_frontend.post("/ingresar", data={"email": "admin@mail.com", "password": "x"})
    assert respuesta.headers["Location"] == "/admin/"


def test_ingresar_con_credenciales_incorrectas_muestra_el_error_y_conserva_el_email(cliente_frontend, llamar):
    llamar.return_value = (None, error_backend(401, "CREDENCIALES_INVALIDAS", "El email o la contraseña son incorrectos."))
    respuesta = cliente_frontend.post("/ingresar", data={"email": "ana@mail.com", "password": "secreta123"})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 401
    assert "El email o la contraseña son incorrectos." in html
    assert 'value="ana@mail.com"' in html
    assert "secreta123" not in html
    with cliente_frontend.session_transaction() as sesion:
        assert "token" not in sesion


def test_ingresar_con_el_backend_caido_muestra_un_aviso(cliente_frontend):
    with patch("src.frontend.api_client.requests.request", side_effect=requests.ConnectionError):
        respuesta = cliente_frontend.post("/ingresar", data={"email": "ana@mail.com", "password": "x"})
    assert respuesta.status_code == 503
    assert "No se pudo conectar con el servidor." in respuesta.get_data(as_text=True)


def test_registro_crea_la_cuenta_e_inicia_sesion(cliente_frontend, llamar):
    llamar.side_effect = [({"id": 7, "rol": "cliente"}, None), ({"token": "t", "rol": "cliente", "nombre": "Ana Pérez"}, None)]
    respuesta = cliente_frontend.post("/registro", data=REGISTRO_VALIDO)
    assert respuesta.headers["Location"] == "/"
    assert llamar.call_args_list[0].args == ("POST", "/api/auth/registro")
    assert llamar.call_args_list[0].kwargs["json"] == {"nombre": "Ana Pérez", "email": "ana@mail.com",
                                                       "password": "secreta123"}
    assert llamar.call_args_list[1].args == ("POST", "/api/auth/login")
    with cliente_frontend.session_transaction() as sesion:
        assert sesion["token"] == "t"


def test_registro_con_email_repetido_muestra_el_error_sin_iniciar_sesion(cliente_frontend, llamar):
    llamar.return_value = (None, error_backend(409, "EMAIL_REGISTRADO", "Ya existe una cuenta con ese email."))
    respuesta = cliente_frontend.post("/registro", data=REGISTRO_VALIDO)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert "Ya existe una cuenta con ese email." in html
    assert 'value="Ana Pérez"' in html and 'value="ana@mail.com"' in html
    assert "secreta123" not in html
    llamar.assert_called_once()


def test_formulario_invalido_no_llama_al_backend(cliente_frontend, llamar):
    cliente_frontend.post("/ingresar", data={"email": "", "password": ""})
    llamar.assert_not_called()


def test_salir_limpia_la_sesion(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="t", rol="cliente", nombre="Ana")
    respuesta = cliente_frontend.post("/salir", follow_redirects=True)
    assert "Cerraste la sesión." in respuesta.get_data(as_text=True)
    with cliente_frontend.session_transaction() as sesion:
        assert "token" not in sesion


def test_header_con_sesion_muestra_salir(cliente_frontend, backend_ok):
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="t", rol="cliente", nombre="Ana")
    html = cliente_frontend.get("/").get_data(as_text=True)
    assert '<form method="post" action="/salir">' in html
    assert 'href="/ingresar">Ingresar</a>' not in html


def test_header_enlaza_a_ingresar(cliente_frontend, backend_ok):
    html = cliente_frontend.get("/").get_data(as_text=True)
    assert 'class="boton boton-secundario" href="/ingresar">Ingresar</a>' in html


# --- validaciones ---
def test_leer_formulario_recorta_espacios_salvo_en_contrasenas():
    datos = leer_formulario({"email": "  ana@mail.com ", "password": " clave "}, "email", "password", "nombre")
    assert datos == {"email": "ana@mail.com", "password": " clave ", "nombre": ""}


def test_login_valido_no_tiene_errores():
    assert validar_login({"email": "ana@mail.com", "password": "x"}) == {}


@pytest.mark.parametrize("datos, esperado", [
    ({"email": "", "password": ""}, {"email": "Ingresá tu email.", "password": "Ingresá tu contraseña."}),
    ({"email": "ana", "password": "x"}, {"email": EMAIL_INVALIDO}),
    ({"email": "ana@mail", "password": "x"}, {"email": EMAIL_INVALIDO}),
    ({"email": "a@" + "m" * 150 + ".com", "password": "x"}, {"email": EMAIL_INVALIDO}),
])
def test_login_invalido(datos, esperado):
    assert validar_login(datos) == esperado


def test_registro_valido_no_tiene_errores():
    assert validar_registro(REGISTRO_VALIDO) == {}


@pytest.mark.parametrize("cambios, campo, mensaje", [
    ({"nombre": ""}, "nombre", "Ingresá tu nombre."),
    ({"nombre": "a" * 101}, "nombre", "El nombre puede tener hasta 100 caracteres."),
    ({"email": "ana.mail.com"}, "email", EMAIL_INVALIDO),
    ({"password": "1234567", "repetir_password": "1234567"}, "password",
     "La contraseña debe tener al menos 8 caracteres."),
    ({"repetir_password": "otra-clave"}, "repetir_password", "Las contraseñas no coinciden."),
])
def test_registro_invalido(cambios, campo, mensaje):
    assert validar_registro(dict(REGISTRO_VALIDO, **cambios)) == {campo: mensaje}
