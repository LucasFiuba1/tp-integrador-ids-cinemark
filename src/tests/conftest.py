"""Fixtures compartidas por las pruebas (pytest). Reemplazan los setUp repetidos en cada archivo.

Las pruebas comunes no necesitan MySQL, TMDB ni servidores levantados: la base y requests se simulan con
unittest.mock. Las de MySQL real (`*_mysql.py`) usan las fixtures de la sección "MySQL de pruebas" y se saltean
si no hay `.env.test` (SCRUM-78).
"""
from unittest.mock import DEFAULT, Mock, patch

import pytest
from flask import render_template_string

from src.frontend.app import create_app as crear_frontend
from src.tests import mysql_pruebas as base_pruebas
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


# --- MySQL de pruebas (SCRUM-78) ---
# Base real separada de la de desarrollo, recreada con schema.sql + seed.sql una vez por corrida.
@pytest.fixture(scope="session")
def mysql_pruebas():
    """Config de la base de pruebas ya recreada; si no hay `.env.test`, saltea la prueba que la pide."""
    config = base_pruebas.leer_config()
    if config is None:
        pytest.skip("Sin base MySQL de pruebas: copiar .env.test.example a .env.test y completarlo.")
    base_pruebas.recrear_base(config)
    return config


@pytest.fixture
def app_mysql(mysql_pruebas):
    """App del backend conectada a la base de pruebas, con su contexto activo."""
    with contexto_app_backend(**mysql_pruebas) as app:
        yield app


@pytest.fixture
def cliente_http(app_mysql):
    return app_mysql.test_client()


def _iniciar_sesion(cliente, credenciales):
    """Login real contra la base de pruebas; devuelve el token."""
    respuesta = cliente.post("/api/auth/login", json=credenciales)
    assert respuesta.status_code == 200, respuesta.get_json()
    return respuesta.get_json()["token"]


@pytest.fixture
def token_admin(cliente_http):
    return _iniciar_sesion(cliente_http, base_pruebas.ADMIN_SEED)


@pytest.fixture
def token_cliente(cliente_http):
    """Token de Ana, cliente del seed."""
    return _iniciar_sesion(cliente_http, base_pruebas.CLIENTES_SEED[0])


@pytest.fixture
def token_otro_cliente(cliente_http):
    """Token de Juan, otro cliente del seed (para pedidos que compiten con los de Ana)."""
    return _iniciar_sesion(cliente_http, base_pruebas.CLIENTES_SEED[1])


@pytest.fixture
def fabrica_funciones(mysql_pruebas):
    """Crea funciones de una película propia de la prueba, con commit real (las ven otros hilos y conexiones).

    Devuelve {"pelicula_id", "crear"}; `crear(fecha_hora, sala_id=1)` inserta una función y devuelve su id y sus
    primeras cuatro butacas. Al terminar borra todo lo que cuelga de esa película (también lo creado por la API).
    """
    conexion = base_pruebas.conectar(mysql_pruebas)
    pelicula_id = base_pruebas.ejecutar(
        conexion,
        "INSERT INTO peliculas (tmdb_id, titulo, sinopsis, duracion_min, clasificacion, genero, "
        "disponible_desde, disponible_hasta) "
        "VALUES (%s, 'Película de prueba', 'Solo para pruebas.', 120, 'ATP', 'Drama', %s, %s)",
        (base_pruebas.TMDB_ID_PRUEBA, "2020-01-01 00:00:00", "2035-12-31 23:59:59"),
    )

    def crear(fecha_hora, sala_id=1):
        funcion_id = base_pruebas.ejecutar(
            conexion, "INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio) VALUES (%s, %s, %s, 5000)",
            (pelicula_id, sala_id, fecha_hora),
        )
        butacas = base_pruebas.filas(
            conexion, "SELECT id, fila, numero FROM butacas WHERE sala_id = %s ORDER BY fila, numero LIMIT 4",
            (sala_id,),
        )
        return {"id": funcion_id, "butaca_ids": [butaca["id"] for butaca in butacas]}

    try:
        yield {"pelicula_id": pelicula_id, "crear": crear}
    finally:
        base_pruebas.borrar_pelicula_de_prueba(conexion, pelicula_id)
        conexion.close()


@pytest.fixture
def funcion_con_butacas(fabrica_funciones):
    """Una función futura (2031) en la sala 1 con sus primeras cuatro butacas libres."""
    return fabrica_funciones["crear"]("2031-06-10 21:00:00")
