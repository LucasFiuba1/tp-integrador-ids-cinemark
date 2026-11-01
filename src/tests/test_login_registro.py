"""Pruebas de los templates maquetados de ingresar y crear cuenta (SCRUM-88)."""
import unittest
from flask import render_template

from src.frontend.app import create_app as crear_frontend
from src.frontend.validaciones import leer_formulario, validar_login, validar_registro

REGISTRO_VALIDO = {"nombre": "Ana Pérez", "email": "ana@mail.com", "password": "secreta123",
                   "repetir_password": "secreta123"}


class LoginRegistroTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.app = app
        self.cliente = app.test_client()

    def test_ingresar_muestra_el_formulario_con_la_pestana_activa(self):
        respuesta = self.cliente.get("/ingresar")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("¡Hola de nuevo!", html)
        self.assertIn('<form method="post" action="/ingresar"', html)
        self.assertIn('href="/ingresar" aria-current="page"', html)
        self.assertIn('name="email" value="" placeholder="tu@email.com" autocomplete="email" required', html)
        self.assertIn('type="password" name="password"', html)

    def test_registro_muestra_los_cuatro_campos(self):
        respuesta = self.cliente.get("/registro")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Creá tu cuenta", html)
        self.assertIn('href="/registro" aria-current="page"', html)
        for nombre in ("nombre", "email", "password", "repetir_password"):
            with self.subTest(nombre=nombre):
                self.assertIn(f'name="{nombre}"', html)
        self.assertEqual(html.count('minlength="8"'), 2)

    def test_formularios_desactivan_la_validacion_del_navegador(self):
        for ruta in ("/ingresar", "/registro"):
            with self.subTest(ruta=ruta):
                self.assertIn('class="auth-formulario" novalidate>', self.cliente.get(ruta).get_data(as_text=True))

    def test_ingresar_con_email_invalido_muestra_el_error_en_el_campo(self):
        respuesta = self.cliente.post("/ingresar", data={"email": "4r", "password": "secreta123"})
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('<label class="campo campo-invalido">', html)
        self.assertIn('value="4r"', html)
        self.assertIn('aria-invalid="true" aria-describedby="error-email"', html)
        self.assertIn('id="error-email">Ingresá un email válido, por ejemplo nombre@mail.com.</small>', html)
        self.assertIn("Revisá los datos marcados", html)
        self.assertNotIn("secreta123", html)

    def test_registro_con_errores_conserva_nombre_y_email(self):
        datos = dict(REGISTRO_VALIDO, password="corta", repetir_password="otra")
        html = self.cliente.post("/registro", data=datos).get_data(as_text=True)
        self.assertIn('value="Ana Pérez"', html)
        self.assertIn('value="ana@mail.com"', html)
        self.assertIn("al menos 8 caracteres", html)
        self.assertIn("Las contraseñas no coinciden.", html)
        self.assertNotIn('value="corta"', html)

    def test_header_enlaza_a_ingresar(self):
        with self.app.test_request_context("/"):
            html = render_template("base.html")
        self.assertIn('class="boton boton-secundario" href="/ingresar">Ingresar</a>', html)


class ValidacionesTest(unittest.TestCase):
    def test_leer_formulario_recorta_espacios_salvo_en_contrasenas(self):
        datos = leer_formulario({"email": "  ana@mail.com ", "password": " clave "}, "email", "password", "nombre")
        self.assertEqual(datos, {"email": "ana@mail.com", "password": " clave ", "nombre": ""})

    def test_login_valido_no_tiene_errores(self):
        self.assertEqual(validar_login({"email": "ana@mail.com", "password": "x"}), {})

    def test_login_invalido(self):
        casos = (
            ({"email": "", "password": ""}, {"email": "Ingresá tu email.", "password": "Ingresá tu contraseña."}),
            ({"email": "ana", "password": "x"}, {"email": "Ingresá un email válido, por ejemplo nombre@mail.com."}),
            ({"email": "ana@mail", "password": "x"}, {"email": "Ingresá un email válido, por ejemplo nombre@mail.com."}),
            ({"email": "a@" + "m" * 150 + ".com", "password": "x"},
             {"email": "Ingresá un email válido, por ejemplo nombre@mail.com."}),
        )
        for datos, esperado in casos:
            with self.subTest(datos=datos):
                self.assertEqual(validar_login(datos), esperado)

    def test_registro_valido_no_tiene_errores(self):
        self.assertEqual(validar_registro(REGISTRO_VALIDO), {})

    def test_registro_invalido(self):
        casos = (
            ({"nombre": ""}, "nombre", "Ingresá tu nombre."),
            ({"nombre": "a" * 101}, "nombre", "El nombre puede tener hasta 100 caracteres."),
            ({"email": "ana.mail.com"}, "email", "Ingresá un email válido, por ejemplo nombre@mail.com."),
            ({"password": "1234567", "repetir_password": "1234567"}, "password",
             "La contraseña debe tener al menos 8 caracteres."),
            ({"repetir_password": "otra-clave"}, "repetir_password", "Las contraseñas no coinciden."),
        )
        for cambios, campo, mensaje in casos:
            with self.subTest(campo=campo, cambios=cambios):
                self.assertEqual(validar_registro(dict(REGISTRO_VALIDO, **cambios)), {campo: mensaje})


if __name__ == "__main__":
    unittest.main()
