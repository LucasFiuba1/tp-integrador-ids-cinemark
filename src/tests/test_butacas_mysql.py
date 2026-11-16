"""Bloqueo y liberación de varias butacas contra MySQL real (SCRUM-62, SCRUM-69, SCRUM-70). Prueba OPT-IN.

Recorre lo que pasa cuando un cliente elige dos butacas: quedan bloqueadas las dos para los demás, un pedido que
pisa una sola de ellas se rechaza sin bloquear las otras, y vencer o cancelar la compra libera las dos juntas.
Usa la base MySQL de pruebas (SCRUM-78), recreada con el seed. Todo corre en una única transacción que termina
siempre en rollback (fixture `conexion`): la función y los clientes se insertan ahí (año 2031) y la base queda como estaba.

    python -m pytest src/tests/test_butacas_mysql.py -v      # requiere .env.test (ver .env.test.example)
"""
from unittest.mock import patch

import pytest

from src.tests.mysql_pruebas import conexion_con_rollback, ejecutar as _ejecutar, filas as _filas
from src.tests.utilidades import cabeceras_de, simular_usuarios


# --- infraestructura (base de pruebas de SCRUM-78, ver src/tests/mysql_pruebas.py) ---
@pytest.fixture(autouse=True)
def mysql_real(app_backend, mysql_pruebas):
    """Apunta la app de pruebas a la base MySQL de pruebas: `src.backend.db` real, solo cambia la conexión."""
    app_backend.config.update(mysql_pruebas)


@pytest.fixture
def conexion(mysql_real):
    """Las consultas del backend usan una única conexión sin commit: lo insertado se ve y al final se deshace."""
    with conexion_con_rollback() as conexion:
        yield conexion


SALA = 1  # sala del seed con butacas
FECHA_FUNCION = "2031-06-10 21:00:00"


def _cliente(conexion, email):
    usuario_id = _ejecutar(
        conexion, "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, 'x', 'cliente')",
        (email.split("@")[0], email),
    )
    return {"id": usuario_id, "nombre": email.split("@")[0], "email": email, "rol": "cliente"}


@pytest.fixture
def escenario(conexion, app_backend):
    """Una función futura en la sala 1, sus primeras cuatro butacas y dos clientes con su token."""
    pelicula_id = _filas(conexion, "SELECT id FROM peliculas WHERE activa = TRUE ORDER BY id LIMIT 1")[0]["id"]
    _ejecutar(conexion, "UPDATE peliculas SET disponible_hasta = '2031-12-31 23:59:59' WHERE id = %s", (pelicula_id,))
    funcion_id = _ejecutar(
        conexion, "INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio) VALUES (%s, %s, %s, 5000)",
        (pelicula_id, SALA, FECHA_FUNCION),
    )
    butacas = _filas(conexion, "SELECT id, fila, numero FROM butacas WHERE sala_id = %s ORDER BY fila, numero LIMIT 4",
                     (SALA,))
    ana, beto = _cliente(conexion, "ana.prueba@mail.test"), _cliente(conexion, "beto.prueba@mail.test")
    with simular_usuarios(ana, beto):
        yield {
            "conexion": conexion, "funcion_id": funcion_id, "butacas": butacas,
            "nombres": [f"{butaca['fila']}{butaca['numero']}" for butaca in butacas],
            "ana": cabeceras_de(ana), "beto": cabeceras_de(beto),
        }


def _reservar(cliente, escenario, quien, indices):
    ids = [escenario["butacas"][indice]["id"] for indice in indices]
    return cliente.post("/api/compras", json={"funcion_id": escenario["funcion_id"], "butaca_ids": ids},
                        headers=escenario[quien])


def _estados(cliente, escenario):
    """{nombre de butaca: estado} de las cuatro butacas del escenario, según el mapa público."""
    mapa = cliente.get(f"/api/funciones/{escenario['funcion_id']}/butacas").get_json()
    estados = {f"{butaca['fila']}{butaca['numero']}": butaca["estado"] for butaca in mapa["butacas"]}
    return [estados[nombre] for nombre in escenario["nombres"]]


def _vencer(escenario, compra_id):
    _ejecutar(escenario["conexion"], "UPDATE compras SET vence_en = NOW() - INTERVAL 1 MINUTE WHERE id = %s",
              (compra_id,))


# --- bloqueo ---
def test_reservar_dos_butacas_bloquea_las_dos(cliente_backend, escenario):
    respuesta = _reservar(cliente_backend, escenario, "ana", [0, 1])
    assert respuesta.status_code == 201, respuesta.get_json()
    assert respuesta.get_json()["subtotal_entradas"] == 10000.0
    assert _estados(cliente_backend, escenario) == ["ocupada", "ocupada", "libre", "libre"]
    detalle = cliente_backend.get(f"/api/compras/{respuesta.get_json()['id']}", headers=escenario["ana"]).get_json()
    assert detalle["butacas"] == escenario["nombres"][:2]


def test_otro_cliente_que_pisa_una_de_las_dos_recibe_409_y_no_bloquea_la_otra(cliente_backend, escenario):
    _reservar(cliente_backend, escenario, "ana", [0, 1])
    respuesta = _reservar(cliente_backend, escenario, "beto", [1, 2])
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "BUTACA_OCUPADA"
    assert escenario["nombres"][1] in respuesta.get_json()["error"]["mensaje"]
    assert escenario["nombres"][2] not in respuesta.get_json()["error"]["mensaje"]
    assert _estados(cliente_backend, escenario) == ["ocupada", "ocupada", "libre", "libre"]
    assert _reservar(cliente_backend, escenario, "beto", [2, 3]).status_code == 201
    assert _estados(cliente_backend, escenario) == ["ocupada"] * 4


def test_el_mismo_cliente_tampoco_puede_reservar_dos_veces_la_misma_butaca(cliente_backend, escenario):
    _reservar(cliente_backend, escenario, "ana", [0, 1])
    assert _reservar(cliente_backend, escenario, "ana", [1]).status_code == 409


# --- liberación ---
def test_al_vencer_la_reserva_se_liberan_las_dos_y_otro_puede_tomarlas(cliente_backend, escenario):
    compra_id = _reservar(cliente_backend, escenario, "ana", [0, 1]).get_json()["id"]
    _vencer(escenario, compra_id)
    assert _estados(cliente_backend, escenario) == ["libre"] * 4
    assert _reservar(cliente_backend, escenario, "beto", [0, 1]).status_code == 201
    assert _estados(cliente_backend, escenario) == ["ocupada", "ocupada", "libre", "libre"]
    vieja = cliente_backend.get(f"/api/compras/{compra_id}", headers=escenario["ana"]).get_json()
    assert vieja["estado"] == "vencida"


def test_pagar_una_reserva_vencida_devuelve_409_y_deja_las_dos_libres(cliente_backend, escenario):
    compra_id = _reservar(cliente_backend, escenario, "ana", [0, 1]).get_json()["id"]
    _vencer(escenario, compra_id)
    respuesta = cliente_backend.post(f"/api/compras/{compra_id}/confirmar", headers=escenario["ana"])
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "RESERVA_VENCIDA"
    activas = _filas(escenario["conexion"], "SELECT COUNT(*) AS n FROM entradas WHERE compra_id = %s AND activa = 1",
                     (compra_id,))
    assert activas[0]["n"] == 0
    assert _estados(cliente_backend, escenario) == ["libre"] * 4


def test_confirmar_mantiene_las_dos_y_cancelar_las_libera_juntas(cliente_backend, escenario):
    compra_id = _reservar(cliente_backend, escenario, "ana", [0, 1]).get_json()["id"]
    with patch("src.backend.services.compras.correo.enviar_factura", return_value=True):
        confirmada = cliente_backend.post(f"/api/compras/{compra_id}/confirmar", headers=escenario["ana"])
    assert confirmada.status_code == 200, confirmada.get_json()
    _vencer(escenario, compra_id)  # una compra confirmada no vence: las butacas siguen ocupadas
    assert _estados(cliente_backend, escenario) == ["ocupada", "ocupada", "libre", "libre"]
    assert _reservar(cliente_backend, escenario, "beto", [0]).status_code == 409

    cancelada = cliente_backend.post(f"/api/compras/{compra_id}/cancelar", headers=escenario["ana"])
    assert cancelada.status_code == 200, cancelada.get_json()
    assert _estados(cliente_backend, escenario) == ["libre"] * 4
    assert _reservar(cliente_backend, escenario, "beto", [0, 1]).status_code == 201
