"""Fixtures compartidas por las pruebas (pytest). Reemplazan los setUp repetidos en cada archivo.

Ninguna prueba necesita MySQL, TMDB ni servidores levantados: la base y requests se simulan con unittest.mock.
"""
from unittest.mock import Mock, patch

import pytest
from flask import render_template_string

from src.backend.app import create_app as crear_backend
from src.backend.auth import generar_token
from src.frontend.app import create_app as crear_frontend


# --- backend ---
@pytest.fixture
def app_backend():
    app = crear_backend()
    app.config.update(TESTING=True, SECRET_KEY="pruebas", TMDB_API_KEY="clave-de-prueba")
    with app.app_context():
        yield app


@pytest.fixture
def cliente_backend(app_backend):
    return app_backend.test_client()


@pytest.fixture
def usuario():
    """Usuario que devuelve la base simulada al validar el token. Cambiar usuario["rol"] para probar permisos."""
    usuario = {"id": 1, "nombre": "Admin", "rol": "admin"}
    with patch("src.backend.auth.consultar_uno", return_value=usuario):
        yield usuario


@pytest.fixture
def cabeceras(app_backend, usuario):
    return {"Authorization": f"Bearer {generar_token(usuario['id'])}"}


# --- frontend ---
@pytest.fixture
def app_frontend():
    app = crear_frontend()
    app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test")
    return app


@pytest.fixture
def cliente_frontend(app_frontend):
    return app_frontend.test_client()


@pytest.fixture
def cliente_admin(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion["rol"] = "admin"
    return cliente_frontend


@pytest.fixture
def backend_ok():
    """Simula que el backend responde {"estado": "ok"} a cualquier llamada."""
    with patch("src.frontend.api_client.requests.request") as peticion:
        peticion.return_value = Mock(ok=True, content=b'{"estado":"ok"}')
        peticion.return_value.json.return_value = {"estado": "ok"}
        yield peticion


@pytest.fixture
def renderizar(app_frontend):
    """Renderiza un template de prueba (por ejemplo, una macro) dentro de un request del frontend."""
    def renderizar_plantilla(plantilla, **contexto):
        with app_frontend.test_request_context():
            return render_template_string(plantilla, **contexto)
    return renderizar_plantilla
