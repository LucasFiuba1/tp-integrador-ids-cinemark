"""Pruebas de locales y salas (SCRUM-54) con la base simulada. Se corren con pytest."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from src.backend.app import create_app
from src.backend.auth import generar_token
from src.backend.services import salas


@contextmanager
def transaccion_falsa(cursor):
    yield cursor


@pytest.fixture
def pedir():
    """Devuelve una función que hace pedidos a la API fingiendo un usuario con el rol dado."""
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="pruebas")
    cliente = app.test_client()

    def hacer_pedido(metodo, ruta, datos=None, rol="admin", con_token=True):
        usuario = {"id": 1, "nombre": "Usuario", "rol": rol}
        cabeceras = {}
        with patch("src.backend.auth.consultar_uno", return_value=usuario):
            if con_token:
                with app.app_context():
                    cabeceras = {"Authorization": f"Bearer {generar_token(1)}"}
            return cliente.open(ruta, method=metodo, json=datos, headers=cabeceras)

    return hacer_pedido


@pytest.fixture
def db_locales():
    with patch("src.backend.services.locales.db") as db:
        yield db


@pytest.fixture
def db_salas():
    with patch("src.backend.services.salas.db") as db:
        yield db


@pytest.fixture
def cursor(db_salas):
    """Cursor falso: db.transaccion() lo entrega y así se puede ver qué SQL se ejecutó."""
    cursor = MagicMock(lastrowid=7)

    def abrir_transaccion():
        return transaccion_falsa(cursor)

    db_salas.transaccion.side_effect = abrir_transaccion
    return cursor


@pytest.fixture
def local():
    return {"id": 1, "nombre": "Paradiso Centro", "direccion": "Av. Corrientes 1234, CABA"}


@pytest.fixture
def sala():
    return {"id": 5, "local_id": 1, "local": "Paradiso Centro", "nombre": "Sala 1",
            "filas": 8, "columnas": 12, "capacidad": 96}


def duplicado():
    return pymysql.err.IntegrityError(1062, "Duplicate entry")


# --- seguridad: todas las rutas ---
RUTAS = (
    ("GET", "/api/admin/locales"), ("POST", "/api/admin/locales"),
    ("PUT", "/api/admin/locales/1"), ("DELETE", "/api/admin/locales/1"),
    ("GET", "/api/admin/salas"), ("POST", "/api/admin/salas"),
    ("PUT", "/api/admin/salas/1"), ("DELETE", "/api/admin/salas/1"),
)


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_pedir_sin_token_devuelve_401(pedir, metodo, ruta):
    respuesta = pedir(metodo, ruta, con_token=False)
    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "NO_AUTENTICADO"


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_pedir_con_rol_cliente_devuelve_403(pedir, metodo, ruta):
    respuesta = pedir(metodo, ruta, rol="cliente")
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "SIN_PERMISO"


# --- locales ---
def test_listar_locales_devuelve_200(pedir, db_locales, local):
    db_locales.consultar.return_value = [local]
    respuesta = pedir("GET", "/api/admin/locales")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [local]


def test_crear_local_valido_devuelve_201(pedir, db_locales):
    db_locales.ejecutar.return_value = 4
    datos = {"nombre": "Paradiso Sur", "direccion": "Calle 1"}
    respuesta = pedir("POST", "/api/admin/locales", datos)
    assert respuesta.status_code == 201
    assert respuesta.get_json() == {"id": 4, **datos}
    assert "INSERT INTO locales" in db_locales.ejecutar.call_args.args[0]


@pytest.mark.parametrize("datos", [
    {}, {"nombre": "Sur"}, {"direccion": "Calle 1"}, {"nombre": "", "direccion": "Calle 1"},
])
def test_crear_local_con_datos_invalidos_devuelve_400(pedir, db_locales, datos):
    respuesta = pedir("POST", "/api/admin/locales", datos)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    db_locales.ejecutar.assert_not_called()


def test_crear_local_repetido_devuelve_409(pedir, db_locales):
    db_locales.ejecutar.side_effect = duplicado()
    respuesta = pedir("POST", "/api/admin/locales", {"nombre": "Sur", "direccion": "Calle 1"})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "LOCAL_DUPLICADO"


def test_modificar_local_valido_devuelve_200(pedir, db_locales, local):
    db_locales.consultar_uno.return_value = local
    datos = {"nombre": "Paradiso Nuevo", "direccion": "Calle 9"}
    respuesta = pedir("PUT", "/api/admin/locales/1", datos)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": 1, **datos}
    assert "UPDATE locales" in db_locales.ejecutar.call_args.args[0]


def test_modificar_local_inexistente_devuelve_404(pedir, db_locales):
    db_locales.consultar_uno.return_value = None
    respuesta = pedir("PUT", "/api/admin/locales/999", {"nombre": "X", "direccion": "Y"})
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_modificar_local_sin_nombre_devuelve_400(pedir, db_locales, local):
    db_locales.consultar_uno.return_value = local
    respuesta = pedir("PUT", "/api/admin/locales/1", {"direccion": "Calle 9"})
    assert respuesta.status_code == 400
    db_locales.ejecutar.assert_not_called()


def test_modificar_local_con_datos_de_otro_devuelve_409(pedir, db_locales, local):
    db_locales.consultar_uno.return_value = local
    db_locales.ejecutar.side_effect = duplicado()
    respuesta = pedir("PUT", "/api/admin/locales/1", {"nombre": "Otro", "direccion": "Calle 9"})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "LOCAL_DUPLICADO"


def test_eliminar_local_sin_salas_devuelve_204(pedir, db_locales, local):
    db_locales.consultar_uno.side_effect = [local, None]
    respuesta = pedir("DELETE", "/api/admin/locales/1")
    assert respuesta.status_code == 204
    assert "DELETE FROM locales" in db_locales.ejecutar.call_args.args[0]


def test_eliminar_local_inexistente_devuelve_404(pedir, db_locales):
    db_locales.consultar_uno.return_value = None
    respuesta = pedir("DELETE", "/api/admin/locales/999")
    assert respuesta.status_code == 404


def test_eliminar_local_con_salas_devuelve_409(pedir, db_locales, local):
    db_locales.consultar_uno.side_effect = [local, {"id": 5}]
    respuesta = pedir("DELETE", "/api/admin/locales/1")
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "LOCAL_CON_SALAS"
    db_locales.ejecutar.assert_not_called()


# --- generación de butacas ---
def test_generar_butacas_de_2_filas_y_3_columnas_devuelve_6_butacas():
    esperadas = [(7, "A", 1), (7, "A", 2), (7, "A", 3), (7, "B", 1), (7, "B", 2), (7, "B", 3)]
    assert salas.generar_butacas(7, 2, 3) == esperadas


def test_generar_butacas_al_agrandar_devuelve_solo_las_que_faltan():
    nuevas = salas.generar_butacas(7, 3, 4, 2, 3)
    esperadas = [(7, "A", 4), (7, "B", 4), (7, "C", 1), (7, "C", 2), (7, "C", 3), (7, "C", 4)]
    assert nuevas == esperadas


# --- salas: listado ---
def test_listar_salas_sin_filtro_devuelve_200(pedir, db_salas, sala):
    db_salas.consultar.return_value = [sala]
    respuesta = pedir("GET", "/api/admin/salas")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [sala]
    assert db_salas.consultar.call_args.args[1] == (None, None)


def test_listar_salas_de_un_local_filtra_por_local_id(pedir, db_salas):
    db_salas.consultar.return_value = []
    respuesta = pedir("GET", "/api/admin/salas?local_id=1")
    assert respuesta.status_code == 200
    assert db_salas.consultar.call_args.args[1] == (1, 1)


# --- salas: alta ---
def test_crear_sala_valida_genera_todas_las_butacas(pedir, db_locales, db_salas, cursor, local):
    db_locales.consultar_uno.return_value = local
    datos = {"local_id": 1, "nombre": "Sala 3", "filas": 8, "columnas": 12}
    respuesta = pedir("POST", "/api/admin/salas", datos)
    butacas = cursor.executemany.call_args.args[1]
    assert respuesta.status_code == 201
    assert respuesta.get_json() == {"id": 7, "nombre": "Sala 3", "capacidad": 96}
    assert len(butacas) == 96
    assert butacas[0] == (7, "A", 1)
    assert butacas[-1] == (7, "H", 12)


@pytest.mark.parametrize("cambio", [
    {"filas": 0}, {"filas": -1}, {"filas": 27}, {"filas": "8"},
    {"columnas": 0}, {"columnas": 31}, {"columnas": 2.5}, {"nombre": ""},
])
def test_crear_sala_con_datos_invalidos_devuelve_400(pedir, db_salas, cursor, cambio):
    datos = {"local_id": 1, "nombre": "Sala 3", "filas": 8, "columnas": 12, **cambio}
    respuesta = pedir("POST", "/api/admin/salas", datos)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    cursor.executemany.assert_not_called()


def test_crear_sala_en_local_inexistente_devuelve_404(pedir, db_locales, db_salas, cursor):
    db_locales.consultar_uno.return_value = None
    datos = {"local_id": 999, "nombre": "Sala 3", "filas": 8, "columnas": 12}
    respuesta = pedir("POST", "/api/admin/salas", datos)
    assert respuesta.status_code == 404
    cursor.executemany.assert_not_called()


def test_crear_sala_con_nombre_repetido_devuelve_409(pedir, db_locales, db_salas, cursor, local):
    db_locales.consultar_uno.return_value = local
    cursor.execute.side_effect = duplicado()
    datos = {"local_id": 1, "nombre": "Sala 1", "filas": 8, "columnas": 12}
    respuesta = pedir("POST", "/api/admin/salas", datos)
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "SALA_DUPLICADA"


# --- salas: edición ---
def test_modificar_sala_al_agrandarla_agrega_solo_las_butacas_nuevas(pedir, db_salas, cursor, sala):
    db_salas.consultar_uno.return_value = sala  # 8x12 = 96 butacas
    datos = {"nombre": "Sala 1", "filas": 10, "columnas": 14}
    respuesta = pedir("PUT", "/api/admin/salas/5", datos)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["capacidad"] == 140
    assert len(cursor.executemany.call_args.args[1]) == 44  # 140 - 96


def test_modificar_sala_al_achicarla_sin_funciones_borra_las_butacas_sobrantes(pedir, db_salas, cursor, sala):
    db_salas.consultar_uno.side_effect = [sala, None, None]  # sala, sin funciones, sin entradas
    respuesta = pedir("PUT", "/api/admin/salas/5", {"nombre": "Sala 1", "filas": 6, "columnas": 12})
    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert respuesta.status_code == 200
    assert any("DELETE FROM butacas" in consulta for consulta in consultas)


def test_modificar_sala_inexistente_devuelve_404(pedir, db_salas):
    db_salas.consultar_uno.return_value = None
    respuesta = pedir("PUT", "/api/admin/salas/999", {"nombre": "X", "filas": 3, "columnas": 4})
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_modificar_sala_con_filas_en_cero_devuelve_400(pedir, db_salas, sala):
    db_salas.consultar_uno.return_value = sala
    respuesta = pedir("PUT", "/api/admin/salas/5", {"nombre": "Sala 1", "filas": 0, "columnas": 12})
    assert respuesta.status_code == 400
    db_salas.transaccion.assert_not_called()


def test_achicar_sala_con_funciones_futuras_devuelve_409(pedir, db_salas, sala):
    db_salas.consultar_uno.side_effect = [sala, {"id": 9}]
    respuesta = pedir("PUT", "/api/admin/salas/5", {"nombre": "Sala 1", "filas": 4, "columnas": 12})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "SALA_CON_FUNCIONES"
    db_salas.transaccion.assert_not_called()


def test_achicar_sala_con_entradas_vendidas_devuelve_409(pedir, db_salas, sala):
    db_salas.consultar_uno.side_effect = [sala, None, {"id": 3}]
    respuesta = pedir("PUT", "/api/admin/salas/5", {"nombre": "Sala 1", "filas": 4, "columnas": 12})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "BUTACAS_CON_ENTRADAS"
    db_salas.transaccion.assert_not_called()


def test_agrandar_sala_con_funciones_futuras_devuelve_200(pedir, db_salas, cursor, sala):
    db_salas.consultar_uno.return_value = sala
    respuesta = pedir("PUT", "/api/admin/salas/5", {"nombre": "Sala 1", "filas": 9, "columnas": 12})
    assert respuesta.status_code == 200
    assert db_salas.consultar_uno.call_count == 1  # no hace falta mirar las funciones


def test_modificar_sala_con_nombre_repetido_devuelve_409(pedir, db_salas, cursor, sala):
    db_salas.consultar_uno.return_value = sala
    cursor.execute.side_effect = duplicado()
    respuesta = pedir("PUT", "/api/admin/salas/5", {"nombre": "Sala 2", "filas": 8, "columnas": 12})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "SALA_DUPLICADA"


# --- salas: baja ---
def test_eliminar_sala_sin_funciones_devuelve_204(pedir, db_salas, sala):
    db_salas.consultar_uno.side_effect = [sala, None]
    respuesta = pedir("DELETE", "/api/admin/salas/5")
    assert respuesta.status_code == 204
    assert "UPDATE salas SET activa = FALSE" in db_salas.ejecutar.call_args.args[0]


def test_eliminar_sala_inexistente_devuelve_404(pedir, db_salas):
    db_salas.consultar_uno.return_value = None
    respuesta = pedir("DELETE", "/api/admin/salas/999")
    assert respuesta.status_code == 404
    db_salas.ejecutar.assert_not_called()


def test_eliminar_sala_con_funciones_futuras_devuelve_409(pedir, db_salas, sala):
    db_salas.consultar_uno.side_effect = [sala, {"id": 9}]
    respuesta = pedir("DELETE", "/api/admin/salas/5")
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "SALA_CON_FUNCIONES"
    db_salas.ejecutar.assert_not_called()