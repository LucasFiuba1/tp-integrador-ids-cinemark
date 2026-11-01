"""Pruebas del template maquetado del ABM de servicios del backoffice (SCRUM-120)."""
import unittest

from src.frontend.app import create_app as crear_frontend
from src.frontend.filtros import precio
from src.frontend.validaciones import (
    MAXIMO_DESCRIPCION,
    MAXIMO_NOMBRE,
    validar_servicio,
)

SERVICIO_VALIDO = {"nombre": "Combo familiar", "descripcion": "Dos pochoclos y dos gaseosas", "precio": "9500"}


class ServiciosBackofficeTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["rol"] = "admin"

    def test_servicios_sin_sesion_de_admin_redirige_a_la_cartelera(self):
        with self.cliente.session_transaction() as sesion:
            sesion.clear()
        for metodo, ruta in (("get", "/admin/servicios"), ("post", "/admin/servicios"),
                             ("get", "/admin/servicios/1"), ("post", "/admin/servicios/1/baja")):
            with self.subTest(metodo=metodo, ruta=ruta):
                respuesta = getattr(self.cliente, metodo)(ruta)
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.headers["Location"], "/")

    def test_listado_muestra_los_servicios_con_precio_estado_y_acciones(self):
        respuesta = self.cliente.get("/admin/servicios")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('href="/admin/servicios" aria-current="page"', html)
        self.assertIn('href="/admin/servicios#formulario-servicio">Nuevo servicio</a>', html)
        for dato in ("Combo pochoclos grande", "Gaseosa de 500 ml", "$6.500", "$8.000"):
            with self.subTest(dato=dato):
                self.assertIn(dato, html)
        self.assertEqual(html.count('class="badge badge-activa">Activo</span>'), 3)
        self.assertIn('class="badge badge-inactiva">Inactivo</span>', html)
        self.assertIn('href="/admin/servicios/4">Editar</a>', html)
        self.assertIn('action="/admin/servicios/1/baja"', html)
        self.assertNotIn('action="/admin/servicios/4/baja"', html)
        self.assertIn(">Quitar</button>", html)

    def test_formulario_de_alta_vacio(self):
        html = self.cliente.get("/admin/servicios").get_data(as_text=True)
        self.assertIn(">Nuevo servicio</h2>", html)
        self.assertIn('<form method="post" action="/admin/servicios" class="formulario-linea" novalidate>', html)
        self.assertIn('type="number" name="precio" value="" placeholder="$0"', html)
        self.assertNotIn(">Cancelar</a>", html)

    def test_editar_carga_el_servicio_en_el_formulario(self):
        html = self.cliente.get("/admin/servicios/2").get_data(as_text=True)
        self.assertIn(">Editar Gaseosa</h2>", html)
        self.assertIn('<form method="post" action="/admin/servicios/2" class="formulario-linea" novalidate>', html)
        self.assertIn('name="descripcion" value="Gaseosa de 500 ml"', html)
        self.assertIn('name="precio" value="2500"', html)
        self.assertIn('href="/admin/servicios">Cancelar</a>', html)

    def test_editar_un_servicio_inexistente_vuelve_al_listado_con_aviso(self):
        respuesta = self.cliente.get("/admin/servicios/99", follow_redirects=True)
        self.assertEqual(respuesta.request.path, "/admin/servicios")
        self.assertIn("Ese servicio no existe.", respuesta.get_data(as_text=True))

    def test_guardar_un_servicio_valido_vuelve_al_listado(self):
        for ruta in ("/admin/servicios", "/admin/servicios/1"):
            with self.subTest(ruta=ruta):
                respuesta = self.cliente.post(ruta, data=SERVICIO_VALIDO, follow_redirects=True)
                self.assertEqual(respuesta.request.path, "/admin/servicios")
                self.assertIn("Guardaste el servicio Combo familiar.", respuesta.get_data(as_text=True))

    def test_guardar_un_servicio_invalido_devuelve_400_con_los_errores(self):
        respuesta = self.cliente.post("/admin/servicios", data={"nombre": " ", "descripcion": "", "precio": "abc"})
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Ingresá el nombre del servicio.", html)
        self.assertIn("El precio tiene que ser un número", html)
        self.assertIn('name="precio" value="abc"', html)

    def test_quitar_un_servicio_avisa_y_vuelve_al_listado(self):
        respuesta = self.cliente.post("/admin/servicios/3/baja", follow_redirects=True)
        self.assertEqual(respuesta.request.path, "/admin/servicios")
        self.assertIn("Quitaste el servicio", respuesta.get_data(as_text=True))


class ValidarServicioTest(unittest.TestCase):
    def test_servicio_valido_no_tiene_errores(self):
        for valor in ("9500", "9500.50", "9500,50"):
            with self.subTest(precio=valor):
                self.assertEqual(validar_servicio({**SERVICIO_VALIDO, "precio": valor}), {})
        self.assertEqual(validar_servicio({**SERVICIO_VALIDO, "descripcion": ""}), {})

    def test_campos_invalidos(self):
        casos = (
            ("nombre", "", "Ingresá el nombre"),
            ("nombre", "x" * (MAXIMO_NOMBRE + 1), "hasta 100 caracteres"),
            ("descripcion", "x" * (MAXIMO_DESCRIPCION + 1), "hasta 255 caracteres"),
            ("precio", "", "Ingresá el precio"),
            ("precio", "doce", "tiene que ser un número"),
            ("precio", "0", "mayor a $0"),
            ("precio", "-10", "mayor a $0"),
            ("precio", "100000000", "menor a $100.000.000"),
        )
        for campo, valor, mensaje in casos:
            with self.subTest(campo=campo, valor=valor[:10]):
                errores = validar_servicio({**SERVICIO_VALIDO, campo: valor})
                self.assertEqual(list(errores), [campo])
                self.assertIn(mensaje, errores[campo])

    def test_filtro_precio_formatea_en_pesos_y_tolera_valores_raros(self):
        self.assertEqual(precio(6500), "$6.500")
        self.assertEqual(precio("1234567.5"), "$1.234.567,50")
        for valor in ("no es número", None):
            with self.subTest(valor=valor):
                self.assertEqual(precio(valor), valor)


if __name__ == "__main__":
    unittest.main()
