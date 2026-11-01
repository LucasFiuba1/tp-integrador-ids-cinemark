"""Pruebas de los templates maquetados de ingresar y crear cuenta (SCRUM-88)."""
import pytest

from src.frontend.validaciones import leer_formulario, validar_login, validar_registro

REGISTRO_VALIDO = {"nombre": "Ana Pérez", "email": "ana@mail.com", "password": "secreta123",
                   "repetir_password": "secreta123"}
EMAIL_INVALIDO = "Ingresá un email válido, por ejemplo nombre@mail.com."


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


@pytest.mark.parametrize("ruta, datos", [
    ("/ingresar", {"email": "ana@mail.com", "password": "x"}),
    ("/registro", REGISTRO_VALIDO),
])
def test_envio_valido_avisa_que_no_esta_habilitado(cliente_frontend, ruta, datos):
    respuesta = cliente_frontend.post(ruta, data=datos, follow_redirects=True)
    assert respuesta.status_code == 200
    assert respuesta.request.path == ruta
    assert "todavía no están habilitados" in respuesta.get_data(as_text=True)


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
