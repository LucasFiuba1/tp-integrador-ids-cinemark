"""Pruebas del layout y los componentes del backoffice (SCRUM-105)."""
import unittest

from flask import render_template_string

from src.frontend.app import create_app as crear_frontend

MACROS = '{% from "macros.html" import tabla, badge_estado, tarjeta_kpi, barra, cabecera_pagina %}'
COLUMNAS = [
    {"clave": "titulo", "titulo": "Título"},
    {"clave": "estado", "titulo": "Estado", "tipo": "estado"},
]
ACCIONES = {"editar": "editar", "baja": "baja"}


class LayoutBackofficeTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()

    def iniciar_sesion(self, rol):
        with self.cliente.session_transaction() as sesion:
            sesion["rol"] = rol

    def test_backoffice_sin_sesion_redirige_a_la_cartelera(self):
        respuesta = self.cliente.get("/admin/peliculas")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/")

    def test_backoffice_con_rol_cliente_redirige_a_la_cartelera(self):
        self.iniciar_sesion("cliente")
        respuesta = self.cliente.get("/admin/dashboards")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/")

    def test_inicio_del_backoffice_redirige_a_dashboards(self):
        self.iniciar_sesion("admin")
        respuesta = self.cliente.get("/admin/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/admin/dashboards")

    def test_sidebar_lista_las_secciones_y_marca_la_actual(self):
        self.iniciar_sesion("admin")
        html = self.cliente.get("/admin/peliculas").get_data(as_text=True)
        for texto in ("Dashboards", "Películas", "Funciones", "Locales y salas", "Servicios", "Validar ingreso"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        self.assertIn('href="/admin/peliculas" aria-current="page"', html)
        self.assertNotIn('href="/admin/funciones" aria-current="page"', html)
        self.assertIn('type="checkbox" id="admin-menu-abierto"', html)
        self.assertNotIn('class="marquesina"', html)

    def test_sidebar_muestra_el_nombre_del_admin(self):
        with self.cliente.session_transaction() as sesion:
            sesion.update(rol="admin", nombre="Lucía")
        html = self.cliente.get("/admin/funciones").get_data(as_text=True)
        self.assertIn("Lucía", html)
        self.assertIn('<form method="post" action="/admin/salir">', html)

    def test_cerrar_sesion_limpia_la_sesion_y_redirige(self):
        self.iniciar_sesion("admin")
        respuesta = self.cliente.post("/admin/salir")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/")
        self.assertEqual(self.cliente.get("/admin/dashboards").status_code, 302)


class ComponentesBackofficeTest(unittest.TestCase):
    def setUp(self):
        self.app = crear_frontend()
        self.app.config.update(TESTING=True, SECRET_KEY="pruebas")
        self.app.add_url_rule("/editar/<int:id>", "editar", lambda id: "")
        self.app.add_url_rule("/baja/<int:id>", "baja", lambda id: "", methods=["POST"])

    def renderizar(self, plantilla, **contexto):
        with self.app.test_request_context():
            return render_template_string(MACROS + plantilla, **contexto)

    def test_tabla_con_filas_muestra_editar_y_baja_por_post(self):
        filas = [{"id": 7, "titulo": "Cinema Paradiso", "estado": "activa", "activa": True}]
        html = self.renderizar("{{ tabla(columnas, filas, acciones) }}", columnas=COLUMNAS, filas=filas,
                               acciones=ACCIONES)
        self.assertIn("Cinema Paradiso", html)
        self.assertIn('href="/editar/7"', html)
        self.assertIn('<form method="post" action="/baja/7">', html)
        self.assertIn('data-etiqueta="Título"', html)

    def test_tabla_no_ofrece_baja_a_filas_inactivas(self):
        filas = [{"id": 3, "titulo": "Nuovo", "estado": "inactiva", "activa": False}]
        html = self.renderizar("{{ tabla(columnas, filas, acciones) }}", columnas=COLUMNAS, filas=filas,
                               acciones=ACCIONES)
        self.assertIn('href="/editar/3"', html)
        self.assertNotIn("/baja/3", html)

    def test_tabla_vacia_muestra_mensaje(self):
        html = self.renderizar("{{ tabla(columnas, [], vacio='No hay películas cargadas.') }}", columnas=COLUMNAS)
        self.assertIn("No hay películas cargadas.", html)
        self.assertNotIn("<table", html)

    def test_badge_estado_muestra_el_estado_en_texto(self):
        for estado in ("activa", "inactiva", "cancelada", "utilizada"):
            with self.subTest(estado=estado):
                html = self.renderizar("{{ badge_estado(estado) }}", estado=estado)
                self.assertIn(f'class="badge badge-{estado}">{estado.capitalize()}</span>', html)

    def test_badge_estado_acepta_otra_leyenda(self):
        html = self.renderizar("{{ badge_estado('activa', 'En cartelera') }}")
        self.assertIn('class="badge badge-activa">En cartelera</span>', html)

    def test_cabecera_pagina_con_y_sin_accion(self):
        html = self.renderizar(
            "{{ cabecera_pagina('Películas', {'texto': 'Importar de TMDB', 'url': '/nueva'}, 'Cartelera del cine') }}"
        )
        self.assertIn("<h1>Películas</h1>", html)
        self.assertIn("Cartelera del cine", html)
        self.assertIn('href="/nueva">Importar de TMDB</a>', html)
        self.assertNotIn("boton", self.renderizar("{{ cabecera_pagina('Funciones') }}"))

    def test_tarjeta_kpi_muestra_titulo_y_valor(self):
        html = self.renderizar("{{ tarjeta_kpi('Entradas vendidas hoy', 312, '▲ 12% vs. ayer', 'positivo') }}")
        self.assertIn("Entradas vendidas hoy", html)
        self.assertIn('<p class="kpi-valor">312</p>', html)
        self.assertIn('<p class="kpi-detalle kpi-positivo">▲ 12% vs. ayer</p>', html)

    def test_barra_calcula_el_ancho_y_lo_limita(self):
        casos = ((30, 120, "25.0%"), (150, 100, "100%"), (5, 0, "0%"))
        for valor, maximo, ancho in casos:
            with self.subTest(valor=valor, maximo=maximo):
                html = self.renderizar("{{ barra('Drama', valor, maximo) }}", valor=valor, maximo=maximo)
                self.assertIn(f"width: {ancho}", html)


if __name__ == "__main__":
    unittest.main()
