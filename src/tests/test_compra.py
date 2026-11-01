"""Pruebas de los templates maquetados de pago y compra confirmada (SCRUM-114)."""
import unittest
from datetime import date

from src.frontend.app import create_app as crear_frontend
from src.frontend.filtros import precio
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
