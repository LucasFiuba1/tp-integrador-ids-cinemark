"""Pruebas del template maquetado de validar ingreso del backoffice (SCRUM-122)."""
import unittest

from flask import render_template_string

from src.frontend.app import create_app as crear_frontend
from src.frontend.filtros import fecha_hora, hora
from src.frontend.validaciones import MAXIMO_CODIGO_QR


class ValidarIngresoTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["rol"] = "admin"

    def test_validar_sin_sesion_de_admin_redirige_a_la_cartelera(self):
        with self.cliente.session_transaction() as sesion:
            sesion.clear()
        for metodo in ("get", "post"):
            with self.subTest(metodo=metodo):
                respuesta = getattr(self.cliente, metodo)("/admin/validar")
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.headers["Location"], "/")

    def test_validar_sin_codigo_muestra_el_formulario_y_el_historial(self):
        respuesta = self.cliente.get("/admin/validar")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('href="/admin/validar" aria-current="page"', html)
        self.assertIn('<form method="post" action="/admin/validar" class="validar-formulario" novalidate>', html)
        self.assertIn('name="codigo" value="" placeholder="CP-1042-D5" autocomplete="off" required autofocus', html)
        self.assertIn("resultado-vacio", html)
        self.assertRegex(html, r'data-etiqueta="Hora">\s*19:12\s*</td>')
        self.assertIn('class="badge badge-ya_utilizada">Ya usada</span>', html)

    def test_codigo_valido_muestra_los_datos_y_el_boton_de_confirmar(self):
        html = self.cliente.post("/admin/validar", data={"codigo": " CP-1042-D5 "}).get_data(as_text=True)
        self.assertIn("resultado-valido", html)
        self.assertIn("Entrada válida", html)
        for dato in ("La noche del telón", "24/10 · 19:30", "Paradiso Centro · Sala 1", "Lucas Berardi", "#1042"):
            with self.subTest(dato=dato):
                self.assertIn(f"<dd>{dato}</dd>", html)
        self.assertIn('<form method="post" action="/admin/validar/confirmar">', html)
        self.assertIn('name="compra_id" value="1042"', html)

    def test_codigo_rechazado_muestra_el_motivo_sin_confirmar(self):
        casos = (("CP-1038-B3", "Este QR ya se usó el 24/10 a las 19:10."),
                 ("XX-0000", "El código no corresponde a ninguna entrada."))
        for codigo, mensaje in casos:
            with self.subTest(codigo=codigo):
                html = self.cliente.post("/admin/validar", data={"codigo": codigo}).get_data(as_text=True)
                self.assertIn("resultado-invalido", html)
                self.assertIn(mensaje, html)
                self.assertNotIn("/admin/validar/confirmar", html)

    def test_codigo_invalido_devuelve_400_con_el_error_en_el_campo(self):
        casos = (("", "Ingresá o escaneá el código de la entrada."),
                 ("x" * (MAXIMO_CODIGO_QR + 1), "El código es demasiado largo"))
        for codigo, mensaje in casos:
            with self.subTest(largo=len(codigo)):
                respuesta = self.cliente.post("/admin/validar", data={"codigo": codigo})
                html = respuesta.get_data(as_text=True)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn('<label class="campo campo-invalido">', html)
                self.assertIn(mensaje, html)
                self.assertIn("resultado-vacio", html)

    def test_confirmar_ingreso_avisa_y_vuelve_a_validar(self):
        casos = (
            ({"compra_id": "1042"}, "Ingreso confirmado"),
            ({"compra_id": "abc"}, "No se pudo confirmar"),
            ({}, "No se pudo confirmar"),
        )
        for datos, mensaje in casos:
            with self.subTest(datos=datos):
                respuesta = self.cliente.post("/admin/validar/confirmar", data=datos, follow_redirects=True)
                self.assertEqual(respuesta.request.path, "/admin/validar")
                self.assertIn(mensaje, respuesta.get_data(as_text=True))


class FiltrosYMacrosTest(unittest.TestCase):
    def test_filtro_renderiza_opciones_seleccionadas_en_formulario_get(self):
        app = crear_frontend()
        opciones = [{"valor": "", "texto": "Todos"}, {"valor": "1", "texto": "Centro"}]
        with app.test_request_context("/"):
            html = render_template_string(
                '{% from "macros.html" import filtro %}'
                '<form method="get">{{ filtro("local_id", "Sucursal", opciones, "1") }}</form>',
                opciones=opciones,
            )
        self.assertIn('<form method="get">', html)
        self.assertIn('<select name="local_id">', html)
        self.assertIn('<option value="1" selected>', html)
        self.assertIn("Centro", html)

    def test_chip_habilitado_enlaza_a_la_seleccion_de_butacas(self):
        app = crear_frontend()
        funcion = {
            "id": 12, "fecha_hora": "2026-11-10T20:30:00", "sala": "Sala 1",
            "formato": "2D", "idioma": "Castellano", "habilitada": True,
        }
        with app.test_request_context("/"):
            html = render_template_string(
                '{% from "macros.html" import chip_funcion %}{{ chip_funcion(funcion) }}',
                funcion=funcion,
            )
        self.assertIn('href="/funciones/12/butacas"', html)
        for dato in ("20:30", "2D", "Castellano", "Sala 1"):
            with self.subTest(dato=dato):
                self.assertIn(dato, html)

    def test_chip_deshabilitado_no_ofrece_enlace(self):
        app = crear_frontend()
        funcion = {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "sala": "Sala 1", "habilitada": False}
        with app.test_request_context("/"):
            html = render_template_string(
                '{% from "macros.html" import chip_funcion %}{{ chip_funcion(funcion) }}',
                funcion=funcion,
            )
        self.assertIn('aria-disabled="true"', html)
        self.assertNotIn("<a ", html)
        self.assertIn("Sala 1", html)

    def test_filtros_de_fecha_formatean_iso_y_toleran_valores_raros(self):
        self.assertEqual(fecha_hora("2026-10-24T19:30:00"), "24/10 · 19:30")
        self.assertEqual(hora("2026-10-24T19:30:00"), "19:30")
        for valor in ("no es fecha", None, ""):
            with self.subTest(valor=valor):
                self.assertEqual(hora(valor), valor)

    def test_tabla_formatea_horas_y_usa_la_leyenda_del_estado(self):
        app = crear_frontend()
        columnas = [{"clave": "hora", "titulo": "Hora", "tipo": "hora"},
                    {"clave": "resultado", "titulo": "Resultado", "tipo": "estado", "textos": {"valida": "Válida"}}]
        filas = [{"hora": "2026-10-24T19:12:00", "resultado": "valida"}, {"hora": "x", "resultado": "cancelada"}]
        with app.test_request_context():
            html = render_template_string('{% from "macros.html" import tabla %}{{ tabla(c, f) }}', c=columnas, f=filas)
        self.assertIn("19:12", html)
        self.assertIn('class="badge badge-valida">Válida</span>', html)
        self.assertIn('class="badge badge-cancelada">Cancelada</span>', html)


if __name__ == "__main__":
    unittest.main()
