"""Pruebas de locales y salas (SCRUM-54) con la base simulada."""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from src.backend.app import create_app
from src.backend.auth import generar_token
from src.backend.services import salas

SALA_8X12 = {"local_id": 1, "nombre": "Sala 3", "filas": 8, "columnas": 12}


def transaccion_falsa(cursor):
    @contextmanager
    def transaccion():
        yield cursor

    return transaccion


class SalasTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="pruebas")
        self.cliente = self.app.test_client()
        usuario = {"id": 1, "nombre": "Admin", "rol": "admin"}
        parche = patch("src.backend.auth.consultar_uno", return_value=usuario)
        parche.start()
        self.addCleanup(parche.stop)
        with self.app.app_context():
            self.cabeceras = {"Authorization": f"Bearer {generar_token(1)}"}

    def test_generar_butacas_de_2_filas_y_3_columnas(self):
        butacas = salas.generar_butacas(7, 2, 3)
        self.assertEqual(butacas, [(7, "A", 1), (7, "A", 2), (7, "A", 3), (7, "B", 1), (7, "B", 2), (7, "B", 3)],)


if __name__ == "__main__":
    unittest.main()