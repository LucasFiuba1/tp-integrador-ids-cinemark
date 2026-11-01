"""Pruebas de los templates maquetados de pago, compra confirmada (SCRUM-114) y cancelación (SCRUM-115)."""
import unittest
from datetime import date
from unittest.mock import patch

from src.frontend.app import create_app as crear_frontend
from src.frontend.filtros import precio
from src.frontend.routes import publico
from src.frontend.validaciones import validar_pago

PAGO_VALIDO = {"titular": "Lucas Berardi", "numero": "4242 4242 4242 4242", "vencimiento": "12/28",
               "codigo_seguridad": "123", "acepto": "si"}


class PagoTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()

    def test_pago_muestra_pasos_formulario_y_resumen(self):
        respuesta = self.cliente.get("/compras/1042/pago")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('<li class="paso paso-hecho">', html)
        self.assertIn('<li class="paso paso-actual" aria-current="step">', html)
        self.assertIn('<form id="formulario-pago" method="post" action="/compras/1042/pago" novalidate>', html)
        for nombre in ("titular", "numero", "vencimiento", "codigo_seguridad", "acepto"):
            with self.subTest(nombre=nombre):
                self.assertIn(f'name="{nombre}"', html)
        self.assertIn('form="formulario-pago">Confirmar y pagar</button>', html)
        for dato in ("La noche del telón", "3 entradas", "Combo pochoclos grande × 1", "$16.500", "$23.000", "19:05"):
            with self.subTest(dato=dato):
                self.assertIn(dato, html)

    def test_pago_valido_redirige_a_compra_confirmada(self):
        respuesta = self.cliente.post("/compras/1042/pago", data=PAGO_VALIDO)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/compras/1042/confirmada")

    def test_pago_con_errores_devuelve_400_sin_repetir_los_datos_de_la_tarjeta(self):
        datos = dict(PAGO_VALIDO, vencimiento="13/28", acepto="")
        respuesta = self.cliente.post("/compras/1042/pago", data=datos)
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('id="error-vencimiento">Ingresá el vencimiento como MM/AA', html)
        self.assertIn('id="error-acepto">Tenés que aceptar', html)
        self.assertIn('value="Lucas Berardi"', html)
        self.assertNotIn('value="4242', html)
        self.assertNotIn('value="123"', html)

    def test_compra_confirmada_muestra_qr_y_datos(self):
        respuesta = self.cliente.get("/compras/1042/confirmada")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("¡Compra confirmada!", html)
        self.assertIn('src="data:image/png;base64,iVBORw0KGgo', html)
        self.assertIn('alt="Código QR de ingreso de la compra #1042"', html)
        for dato in ("Paradiso Centro", "24/10 · 19:30", "D5, D6, D7", "Combo pochoclos grande × 1"):
            with self.subTest(dato=dato):
                self.assertIn(f"<dd>{dato}</dd>", html)
        self.assertIn("<strong>$23.000</strong>", html)
        self.assertIn("lucas@email.com", html)
        self.assertIn('href="/">Volver a cartelera</a>', html)


class CancelarCompraTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()

    def test_muestra_la_compra_y_pide_confirmacion(self):
        respuesta = self.cliente.get("/compras/1042/cancelar")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("<h1>Cancelar compra</h1>", html)
        self.assertNotIn("ticket-qr", html)
        for dato in ("Paradiso Centro", "24/10 · 19:30", "D5, D6, D7", "Combo pochoclos grande × 1"):
            with self.subTest(dato=dato):
                self.assertIn(f"<dd>{dato}</dd>", html)
        self.assertIn("N.º de compra #1042", html)
        self.assertIn("se liberan las butacas", html)
        self.assertIn('method="post"\n        action="/compras/1042/cancelar"', html)
        self.assertIn(">Sí, cancelar compra</button>", html)

    def test_fuera_de_plazo_no_ofrece_cancelar(self):
        compra = dict(publico._compra_ejemplo(1042, confirmada=True), cancelable=False)
        with patch.object(publico, "_compra_ejemplo", return_value=compra):
            html = self.cliente.get("/compras/1042/cancelar").get_data(as_text=True)
        self.assertIn("No se puede cancelar: faltan menos de 2 horas", html)
        self.assertNotIn("<form", html)

    def test_confirmar_redirige_a_la_cartelera_con_aviso(self):
        respuesta = self.cliente.post("/compras/1042/cancelar")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/")
        with self.cliente.session_transaction() as sesion:
            self.assertIn(("exito", "Cancelaste la compra #1042. Liberamos las butacas y el QR ya no es válido."),
                          sesion["_flashes"])


class ValidarPagoTest(unittest.TestCase):
    HOY = date(2026, 10, 31)

    def test_datos_validos_no_tienen_errores(self):
        self.assertEqual(validar_pago(PAGO_VALIDO, self.HOY), {})
        self.assertEqual(validar_pago(dict(PAGO_VALIDO, vencimiento="10/26"), self.HOY), {})

    def test_cada_campo_invalido_tiene_su_mensaje(self):
        casos = (
            ("titular", "", "Ingresá el nombre del titular"),
            ("titular", "x" * 101, "hasta 100 caracteres"),
            ("numero", "", "Ingresá el número"),
            ("numero", "4242 abcd", "entre 13 y 19 dígitos"),
            ("numero", "4242", "entre 13 y 19 dígitos"),
            ("vencimiento", "1228", "MM/AA"),
            ("vencimiento", "09/26", "La tarjeta está vencida."),
            ("codigo_seguridad", "12", "3 o 4 dígitos"),
            ("codigo_seguridad", "12a", "3 o 4 dígitos"),
            ("acepto", "", "Tenés que aceptar"),
        )
        for campo, valor, mensaje in casos:
            with self.subTest(campo=campo, valor=valor):
                errores = validar_pago(dict(PAGO_VALIDO, **{campo: valor}), self.HOY)
                self.assertEqual(list(errores), [campo])
                self.assertIn(mensaje, errores[campo])

    def test_precio_usa_formato_argentino(self):
        self.assertEqual(precio(23000), "$23.000")
        self.assertEqual(precio(6500.5), "$6.500,50")
        self.assertEqual(precio(None), None)


if __name__ == "__main__":
    unittest.main()
