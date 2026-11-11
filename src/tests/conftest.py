"""Fixtures compartidas por las pruebas (pytest). Reemplazan los setUp repetidos en cada archivo.

Ninguna prueba necesita MySQL, TMDB ni servidores levantados: la base y requests se simulan con unittest.mock.
"""
from unittest.mock import DEFAULT, Mock, patch

import pytest
from flask import render_template_string

from src.frontend.app import create_app as crear_frontend
from src.tests.utilidades import (
    LOCALES_API, cabeceras_de, contexto_app_backend, simular_bd, simular_usuarios, usuario_de_prueba,
)


# --- backend ---
# El armado de la app, la base simulada, los usuarios y los tokens viven en src/tests/utilidades.py (SCRUM-101).
@pytest.fixture
def app_backend():
    with contexto_app_backend() as app:
        yield app


@pytest.fixture
def cliente_backend(app_backend):
    return app_backend.test_client()


@pytest.fixture
def bd_simulada():
    """Base simulada solo en src.backend.db. Para un service usar simular_bd(destinos=(...)) en una fixture propia."""
    with simular_bd() as simulacion:
        yield simulacion


@pytest.fixture
def usuarios():
    """Usuarios que conoce la base simulada al validar el token: {"admin": id 1, "cliente": id 2}."""
    admin, cliente = usuario_de_prueba("admin"), usuario_de_prueba("cliente")
    with simular_usuarios(admin, cliente):
        yield {"admin": admin, "cliente": cliente}


@pytest.fixture
def usuario(usuarios):
    """Usuario admin (id 1) que devuelve la base simulada al validar el token. Cambiar usuario["rol"] para probar permisos."""
    return usuarios["admin"]


@pytest.fixture
def cabeceras(app_backend, usuario):
    return cabeceras_de(usuario)


@pytest.fixture
def cabeceras_admin(app_backend, usuarios):
    """Token válido del admin (id 1)."""
    return cabeceras_de(usuarios["admin"])


@pytest.fixture
def cabeceras_cliente(app_backend, usuarios):
    """Token válido del cliente (id 2), distinto del admin: sirve para probar 403 y accesos por rol en la misma prueba."""
    return cabeceras_de(usuarios["cliente"])


# --- frontend ---
def pytest_configure(config):
    config.addinivalue_line("markers", "header_real: el header pide sus selectores al backend (simulado) como en producción.")


@pytest.fixture(autouse=True)
def header_sin_backend(request):
    """Desde SCRUM-82 el header de las pantallas del cliente pide locales y películas al backend cuando la vista no
    se los pasa. Para que las pruebas de cada pantalla sigan contando solo sus propias llamadas a la API, acá esas
    dos consultas devuelven listas vacías. Las pruebas del header usan @pytest.mark.header_real."""
    if request.node.get_closest_marker("header_real"):
        yield
        return
    vacio = {"header_locales": [], "header_peliculas": []}
    with patch("src.frontend.routes.publico._header_diferido", return_value=vacio):
        yield


@pytest.fixture
def app_frontend():
    app = crear_frontend()
    # Se fijan los valores que leen las pruebas para que no dependan del .env de cada integrante.
    app.config.update(TESTING=True, SECRET_KEY="pruebas", BACKEND_URL="http://api.test", BACKEND_TIMEOUT=5)
    return app


@pytest.fixture
def cliente_frontend(app_frontend):
    return app_frontend.test_client()


@pytest.fixture
def cliente_admin(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="token-admin", rol="admin")
    return cliente_frontend


@pytest.fixture
def cliente_logueado(cliente_frontend):
    """Sesión iniciada con rol cliente, para las páginas protegidas con @requiere_sesion."""
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="token-cliente", rol="cliente", nombre="Ana")
    return cliente_frontend


@pytest.fixture
def backend_ok():
    """Simula que el backend responde {"estado": "ok"} a cualquier llamada."""
    with patch("src.frontend.api_client.requests.request") as peticion:
        peticion.return_value = Mock(ok=True, content=b'{"estado":"ok"}')
        peticion.return_value.json.return_value = {"estado": "ok"}
        yield peticion


@pytest.fixture
def llamar_publico():
    """Simula `llamar` en routes/publico.py: GET /api/locales responde LOCALES_API (o lo que se ponga en
    `llamar_publico.locales`), las rutas de `llamar_publico.respuestas` ({ruta: (datos, error)}) responden lo suyo y
    cualquier otra llamada devuelve `llamar_publico.return_value`."""
    def responder(metodo, ruta, **opciones):
        if ruta == "/api/locales":
            return llamar.locales
        return llamar.respuestas.get(ruta, DEFAULT)

    with patch("src.frontend.routes.publico.llamar", side_effect=responder) as llamar:
        llamar.locales = ([dict(local) for local in LOCALES_API], None)
        llamar.respuestas = {}
        yield llamar


@pytest.fixture
def renderizar(app_frontend):
    """Renderiza un template de prueba (por ejemplo, una macro) dentro de un request del frontend."""
    def renderizar_plantilla(plantilla, **contexto):
        with app_frontend.test_request_context():
            return render_template_string(plantilla, **contexto)
    return renderizar_plantilla
