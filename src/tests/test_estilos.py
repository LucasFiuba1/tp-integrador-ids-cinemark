"""Pruebas del design system: los estilos usan solo los tokens de tokens.css (SCRUM-111)."""
import re
from pathlib import Path

CARPETA_CSS = Path(__file__).resolve().parents[1] / "frontend" / "static" / "css"
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(")


def test_estilos_no_usan_colores_literales():
    css = (CARPETA_CSS / "estilos.css").read_text(encoding="utf-8")
    assert COLOR_LITERAL.findall(css) == []


def test_estilos_solo_usan_tokens_definidos():
    tokens = (CARPETA_CSS / "tokens.css").read_text(encoding="utf-8")
    definidos = set(re.findall(r"(--[\w-]+)\s*:", tokens))
    usados = set(re.findall(r"var\((--[\w-]+)\)", (CARPETA_CSS / "estilos.css").read_text(encoding="utf-8")))
    assert usados - definidos == set()


def test_base_carga_tokens_antes_que_estilos(cliente_frontend, backend_ok):
    html = cliente_frontend.get("/").get_data(as_text=True)
    assert html.index("css/tokens.css") < html.index("css/estilos.css")
