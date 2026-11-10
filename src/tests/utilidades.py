"""Utilidades comunes para las pruebas del backend (SCRUM-101).

Solo funciones (sin clases): armado de la app de prueba, simulación de la base, usuarios y cabeceras con token
real firmado por rol, y la aserción del formato de error JSON {"error": {"codigo", "mensaje"}}.

Ninguna utilidad toca MySQL ni TMDB, y todas las simulaciones se deshacen solas al salir del `with`/fixture.
"""
import importlib
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.backend import db
from src.backend.app import create_app as crear_backend
from src.backend.auth import generar_token

OPERACIONES_BD = ("consultar", "consultar_uno", "ejecutar", "transaccion")
ID_ADMIN = 1
ID_CLIENTE = 2


# --- app ---
def crear_app_backend(**config):
    """App del backend lista para pruebas; `config` pisa los valores por defecto (por ejemplo TMDB_API_KEY="")."""
    app = crear_backend()
    app.config.update(TESTING=True, SECRET_KEY="pruebas", TMDB_API_KEY="clave-de-prueba")
    app.config.update(config)
    return app


@contextmanager
def contexto_app_backend(**config):
    """App del backend de prueba con su contexto activo (hace falta para firmar tokens)."""
    app = crear_app_backend(**config)
    with app.app_context():
        yield app


# --- base simulada ---
def _transaccion_simulada(cursor):
    """Imita db.transaccion(): cada llamada devuelve un contexto nuevo que entrega siempre el mismo cursor."""
    @contextmanager
    def transaccion():
        yield cursor

    return Mock(side_effect=lambda: transaccion())


def _conexion_prohibida(*args, **kwargs):
    raise AssertionError("La prueba intentó abrir una conexión real a MySQL.")


@contextmanager
def simular_bd(destinos=()):
    """Simula consultar, consultar_uno, ejecutar y transaccion en src.backend.db y en cada módulo de `destinos`.

    Los services importan estas funciones directamente (`from src.backend.db import consultar`), así que hay que
    parchearlas donde se usan: `destinos` son los módulos a interceptar, por ejemplo
    ("src.backend.services.peliculas",). De cada destino se reemplazan solo las operaciones que importa; si no
    importa ninguna se corta con un error, para no creer que se simuló algo que no se simuló.

    Devuelve un SimpleNamespace con los mocks, que se pueden configurar (return_value / side_effect):
      consultar -> [] | consultar_uno -> None | ejecutar -> 1 | cursor (fetchone None, fetchall [], lastrowid 1)
      transaccion -> contexto que entrega `cursor`, reutilizable en usos consecutivos
      conectar -> guarda que falla si algo intenta abrir una conexión real
    Al salir (incluso por una excepción) se restauran todas las funciones originales.
    """
    cursor = Mock(fetchone=Mock(return_value=None), fetchall=Mock(return_value=[]), lastrowid=1)
    simulacion = SimpleNamespace(
        consultar=Mock(return_value=[]),
        consultar_uno=Mock(return_value=None),
        ejecutar=Mock(return_value=1),
        transaccion=_transaccion_simulada(cursor),
        cursor=cursor,
        conectar=Mock(side_effect=_conexion_prohibida),
    )
    with ExitStack() as pila:
        pila.enter_context(patch.object(db, "_conectar", simulacion.conectar))
        modulos = [db] + [importlib.import_module(destino) for destino in destinos]
        for modulo in modulos:
            reemplazadas = [nombre for nombre in OPERACIONES_BD if hasattr(modulo, nombre)]
            if not reemplazadas:
                raise ValueError(f"El módulo {modulo.__name__} no importa ninguna operación de la base.")
            for nombre in reemplazadas:
                pila.enter_context(patch.object(modulo, nombre, getattr(simulacion, nombre)))
        yield simulacion


# --- usuarios y tokens ---
def usuario_de_prueba(rol):
    """Usuario nuevo con el rol dado ("admin" o "cliente"), con id propio de cada rol."""
    if rol == "admin":
        return {"id": ID_ADMIN, "nombre": "Admin", "rol": "admin"}
    return {"id": ID_CLIENTE, "nombre": "Cliente", "rol": rol}


@contextmanager
def simular_usuarios(*usuarios):
    """Simula la base de usuarios de src.backend.auth: el token resuelve al usuario cuyo `id` coincide.

    Un id desconocido devuelve None (el decorador responde 401). La búsqueda se hace en cada pedido sobre los
    mismos dicts, así que cambiar usuario["rol"] durante la prueba cambia lo que ve la autenticación.
    """
    def buscar(sql, parametros=None):
        usuario_id = parametros[0] if parametros else None
        return next((usuario for usuario in usuarios if usuario["id"] == usuario_id), None)

    with patch("src.backend.auth.consultar_uno", side_effect=buscar) as consultar_uno:
        yield consultar_uno


def cabeceras_de(usuario):
    """Cabecera Authorization con un token real firmado para el id del usuario (requiere contexto de app)."""
    return {"Authorization": f"Bearer {generar_token(usuario['id'])}"}


# --- errores JSON ---
def _es_texto_no_vacio(valor):
    return isinstance(valor, str) and valor.strip() != ""


def afirmar_error_json(respuesta, status, codigo, mensaje=None):
    """Verifica una respuesta de error: status, forma exacta {"error": {"codigo", "mensaje"}} y el código.

    `codigo` y `mensaje` deben ser strings no vacíos; si se pasa `mensaje`, además debe coincidir exactamente.
    """
    assert respuesta.status_code == status, f"Se esperaba status {status} y llegó {respuesta.status_code}."
    cuerpo = respuesta.get_json(silent=True)
    assert isinstance(cuerpo, dict), f"El cuerpo no es un objeto JSON: {cuerpo!r}."
    assert set(cuerpo) == {"error"}, f"El cuerpo debe tener solo la clave 'error': {cuerpo!r}."
    error = cuerpo["error"]
    assert isinstance(error, dict), f"'error' no es un objeto: {error!r}."
    assert set(error) == {"codigo", "mensaje"}, f"'error' debe tener solo 'codigo' y 'mensaje': {error!r}."
    assert _es_texto_no_vacio(error["codigo"]), f"El código es vacío o no es texto: {error['codigo']!r}."
    assert _es_texto_no_vacio(error["mensaje"]), f"El mensaje es vacío o no es texto: {error['mensaje']!r}."
    assert error["codigo"] == codigo, f"Se esperaba el código {codigo!r} y llegó {error['codigo']!r}."
    if mensaje is not None:
        assert error["mensaje"] == mensaje, f"Se esperaba el mensaje {mensaje!r} y llegó {error['mensaje']!r}."


# --- frontend: locales de la cartelera (SCRUM-126) ---
# Respuesta simulada de GET /api/locales: ordenada por nombre, como la devuelve el backend.
LOCALES_API = [
    {"id": 2, "nombre": "Paradiso Belgrano"},
    {"id": 1, "nombre": "Paradiso Centro"},
    {"id": 3, "nombre": "Paradiso Palermo"},
]


def llamadas_sin_locales(llamar):
    """Llamadas al backend de una ruta simulada, sin contar la de GET /api/locales que hacen todas las páginas."""
    return [llamada for llamada in llamar.call_args_list if llamada.args[1:2] != ("/api/locales",)]
