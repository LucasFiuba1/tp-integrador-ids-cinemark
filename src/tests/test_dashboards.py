"""Pruebas del template maquetado de dashboards del backoffice (SCRUM-121)."""
import unittest
from unittest.mock import patch

from src.frontend.app import create_app as crear_frontend
from src.frontend.filtros import numero
from src.frontend.routes import backoffice


class DashboardsTest(unittest.TestCase):
    def setUp(self):
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["rol"] = "admin"

    def test_sin_sesion_de_admin_redirige_a_la_cartelera(self):
        with self.cliente.session_transaction() as sesion:
            sesion.clear()
        respuesta = self.cliente.get("/admin/dashboards")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/")

    def test_muestra_los_kpi_y_los_cuatro_tableros(self):
        respuesta = self.cliente.get("/admin/dashboards")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('href="/admin/dashboards" aria-current="page"', html)
        for valor in ("1.742", "$4.820.000", "68%", "4,2%"):
            with self.subTest(valor=valor):
                self.assertIn(f'<p class="kpi-valor">{valor}</p>', html)
        for titulo in ("Entradas por franja horaria", "Ocupación por película", "Ventas por género",
                       "Cancelaciones por película"):
            with self.subTest(titulo=titulo):
                self.assertIn(f">{titulo}</h2>", html)

    def test_las_variaciones_marcan_si_son_buenas_o_malas(self):
        html = self.cliente.get("/admin/dashboards").get_data(as_text=True)
        self.assertIn('<p class="kpi-detalle kpi-positivo">▲ 12% vs. semana anterior</p>', html)
        self.assertIn('<p class="kpi-detalle kpi-negativo">▼ 3 pts vs. semana anterior</p>', html)
        # Más cancelaciones que la semana anterior es una mala noticia aunque el número suba.
        self.assertIn('<p class="kpi-detalle kpi-negativo">▲ 0,6 pts vs. semana anterior</p>', html)

    def test_la_franja_mas_vendida_se_destaca_y_las_columnas_son_proporcionales(self):
        html = self.cliente.get("/admin/dashboards").get_data(as_text=True)
        self.assertEqual(html.count("columna-destacada"), 1)
        self.assertIn('style="height: calc(100.0% - var(--espacio-5))"', html)
        self.assertIn('style="height: calc(24.3% - var(--espacio-5))"', html)  # 180 de 742
        self.assertIn('<span class="columna-etiqueta">18 a 21 h</span>', html)

    def test_tableros_vacios_no_rompen_la_pagina(self):
        datos = dict(backoffice._dashboards_ejemplo(), franjas_horarias=[], ocupacion=[], ventas_genero=[],
                     cancelaciones=[])
        with patch.object(backoffice, "_dashboards_ejemplo", return_value=datos):
            respuesta = self.cliente.get("/admin/dashboards")
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(html.count("Todavía no hay datos para este período."), 4)
        self.assertNotIn('class="columnas"', html)

    def test_numero_usa_formato_argentino(self):
        self.assertEqual(numero(1742), "1.742")
        self.assertEqual(numero(4.2), "4,2")
        self.assertEqual(numero(74), "74")
        self.assertEqual(numero("sin dato"), "sin dato")


if __name__ == "__main__":
    unittest.main()
