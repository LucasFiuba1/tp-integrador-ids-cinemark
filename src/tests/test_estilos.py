"""Pruebas del design system: los estilos usan solo los tokens de tokens.css (SCRUM-111)."""
import re
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.frontend.app import create_app as crear_frontend

CARPETA_CSS = Path(__file__).resolve().parents[1] / "frontend" / "static" / "css"
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(")


class TokensTest(unittest.TestCase):
    def test_estilos_no_usan_colores_literales(self):
        css = (CARPETA_CSS / "estilos.css").read_text(encoding="utf-8")
        self.assertEqual(COLOR_LITERAL.findall(css), [])

    def test_estilos_solo_usan_tokens_definidos(self):
        tokens = (CARPETA_CSS / "tokens.css").read_text(encoding="utf-8")
        definidos = set(re.findall(r"(--[\w-]+)\s*:", tokens))
        usados = set(re.findall(r"var\((--[\w-]+)\)", (CARPETA_CSS / "estilos.css").read_text(encoding="utf-8")))
        self.assertEqual(usados - definidos, set())

    @patch("src.frontend.api_client.requests.request")
    def test_base_carga_tokens_antes_que_estilos(self, peticion):
        peticion.return_value = Mock(ok=True, content=b'{"estado":"ok"}')
        peticion.return_value.json.return_value = {"estado": "ok"}
        app = crear_frontend()
        app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
        html = app.test_client().get("/").get_data(as_text=True)
        self.assertLess(html.index("css/tokens.css"), html.index("css/estilos.css"))
