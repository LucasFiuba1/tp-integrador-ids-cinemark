import unittest

from src.frontend.app import create_app


class TestLocalesTemplate(unittest.TestCase):

    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True, SECRET_KEY="pruebas")
        self.cliente = app.test_client()

    def test_locales_admin(self):
        with self.cliente.session_transaction() as sesion:
            sesion["rol"] = "admin"

        respuesta = self.cliente.get("/admin/locales")

        self.assertEqual(respuesta.status_code, 200)

        html = respuesta.get_data(as_text=True)

        self.assertIn("Paradiso Centro", html)
        self.assertIn("Paradiso Belgrano", html)
        self.assertIn("Paradiso Palermo", html)
        self.assertIn("Sala VIP", html)


if __name__ == "__main__":
    unittest.main()