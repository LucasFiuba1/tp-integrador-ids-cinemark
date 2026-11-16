"""Reglas críticas del enunciado contra MySQL real: doble venta, concurrencia, superposición, cancelación y QR (SCRUM-79).

Las pruebas con mocks ya cubren cada regla por separado; acá se comprueba que se cumplan de verdad con la base, los
bloqueos (FOR UPDATE) y los índices únicos de schema.sql. Los pedidos pasan por la API y hacen commit real, así
otros hilos los ven; la fixture `fabrica_funciones` borra al final todo lo creado.

    python -m pytest src/tests/test_reglas_criticas_mysql.py -v      # requiere .env.test (ver .env.test.example)
"""
import threading
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.tests import mysql_pruebas as base_pruebas
from src.tests.mysql_pruebas import con_token

VALIDAR_QR = "/api/admin/ingresos/validar"


@pytest.fixture(autouse=True)
def sin_correo():
    """Confirmar y cancelar mandan emails: se simulan para no depender de SMTP."""
    with patch("src.backend.services.compras.correo.enviar_factura", return_value=True), \
            patch("src.backend.services.compras.correo.enviar_cancelacion", return_value=True):
        yield


@pytest.fixture
def ana(token_cliente):
    return con_token(token_cliente)


@pytest.fixture
def juan(token_otro_cliente):
    return con_token(token_otro_cliente)


@pytest.fixture
def admin(token_admin):
    return con_token(token_admin)


@pytest.fixture
def base(mysql_pruebas):
    """Conexión propia de la prueba para mirar el estado real de la base."""
    conexion = base_pruebas.conectar(mysql_pruebas)
    yield conexion
    conexion.close()


def _reservar(cliente, funcion, cabeceras, butaca_ids):
    return cliente.post("/api/compras", json={"funcion_id": funcion["id"], "butaca_ids": butaca_ids},
                        headers=cabeceras)


def _comprar(cliente, funcion, cabeceras, butaca_ids):
    """Reserva y confirma; devuelve el id de la compra."""
    reserva = _reservar(cliente, funcion, cabeceras, butaca_ids)
    assert reserva.status_code == 201, reserva.get_json()
    compra_id = reserva.get_json()["id"]
    confirmada = cliente.post(f"/api/compras/{compra_id}/confirmar", headers=cabeceras)
    assert confirmada.status_code == 200, confirmada.get_json()
    return compra_id


def _token_qr(base, compra_id):
    return base_pruebas.filas(base, "SELECT token_qr FROM compras WHERE id = %s", (compra_id,))[0]["token_qr"]


def _entradas_activas(base, funcion_id, butaca_id):
    return base_pruebas.filas(
        base, "SELECT COUNT(*) AS n FROM entradas WHERE funcion_id = %s AND butaca_id = %s AND activa = 1",
        (funcion_id, butaca_id),
    )[0]["n"]


def _codigo(respuesta):
    return respuesta.get_json()["error"]["codigo"]


# --- doble venta y concurrencia ---
def _reservas_simultaneas(app, funcion, pedidos):
    """Lanza un POST /api/compras por pedido `(cabeceras, butaca_ids)`, todos a la vez (Barrier), cada uno en su
    hilo con su propio cliente HTTP y su propia conexión a la base. Devuelve las respuestas en el mismo orden."""
    largada = threading.Barrier(len(pedidos))
    respuestas = [None] * len(pedidos)

    def pedir(indice, cabeceras, butaca_ids):
        cliente = app.test_client()
        largada.wait()
        respuestas[indice] = _reservar(cliente, funcion, cabeceras, butaca_ids)

    hilos = [threading.Thread(target=pedir, args=(indice, cabeceras, butaca_ids))
             for indice, (cabeceras, butaca_ids) in enumerate(pedidos)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    return respuestas


def test_dos_compras_simultaneas_de_la_misma_butaca_solo_una_se_confirma(
        app_mysql, cliente_http, funcion_con_butacas, ana, juan, base):
    butaca = funcion_con_butacas["butaca_ids"][0]
    respuestas = _reservas_simultaneas(app_mysql, funcion_con_butacas, [(ana, [butaca]), (juan, [butaca])])

    estados = sorted(respuesta.status_code for respuesta in respuestas)
    assert estados == [201, 409], [respuesta.get_json() for respuesta in respuestas]
    perdedora = next(respuesta for respuesta in respuestas if respuesta.status_code == 409)
    assert _codigo(perdedora) == "BUTACA_OCUPADA"
    assert _entradas_activas(base, funcion_con_butacas["id"], butaca) == 1

    ganadora = respuestas.index(next(respuesta for respuesta in respuestas if respuesta.status_code == 201))
    cabeceras_ganadora = [ana, juan][ganadora]
    compra_id = respuestas[ganadora].get_json()["id"]
    assert cliente_http.post(f"/api/compras/{compra_id}/confirmar", headers=cabeceras_ganadora).status_code == 200
    assert _reservar(cliente_http, funcion_con_butacas, [juan, ana][ganadora], [butaca]).status_code == 409


def test_ocho_pedidos_simultaneos_con_butacas_cruzadas_no_venden_ninguna_dos_veces(
        app_mysql, funcion_con_butacas, ana, juan, base):
    """Cada pedido pide dos butacas que se pisan con las del siguiente: ninguna puede quedar vendida dos veces."""
    butacas = funcion_con_butacas["butaca_ids"]
    pedidos = [([ana, juan][indice % 2], [butacas[indice % 4], butacas[(indice + 1) % 4]]) for indice in range(8)]
    respuestas = _reservas_simultaneas(app_mysql, funcion_con_butacas, pedidos)

    assert all(respuesta.status_code in (201, 409) for respuesta in respuestas), \
        [respuesta.get_json() for respuesta in respuestas]
    assert any(respuesta.status_code == 201 for respuesta in respuestas)
    assert all(_entradas_activas(base, funcion_con_butacas["id"], butaca) <= 1 for butaca in butacas)
    vendidas = sum(len(pedidos[indice][1]) for indice, respuesta in enumerate(respuestas) if respuesta.status_code == 201)
    assert vendidas == sum(_entradas_activas(base, funcion_con_butacas["id"], butaca) for butaca in butacas)


def test_el_indice_unico_frena_la_doble_venta_aunque_se_saltee_la_api(funcion_con_butacas, base):
    """Última línea de defensa: UNIQUE (funcion_id, butaca_id, activa) en entradas."""
    usuario_id = base_pruebas.filas(base, "SELECT id FROM usuarios WHERE email = 'ana@mail.com'")[0]["id"]
    insertar_compra = ("INSERT INTO compras (usuario_id, funcion_id, estado, total, vence_en) "
                       "VALUES (%s, %s, 'pendiente', 5000, NOW() + INTERVAL 10 MINUTE)")
    insertar_entrada = ("INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio, activa) "
                        "VALUES (%s, %s, %s, 5000, 1)")
    butaca = funcion_con_butacas["butaca_ids"][0]
    for intento in range(2):
        compra_id = base_pruebas.ejecutar(base, insertar_compra, (usuario_id, funcion_con_butacas["id"]))
        if intento == 0:
            base_pruebas.ejecutar(base, insertar_entrada, (compra_id, funcion_con_butacas["id"], butaca))
    with pytest.raises(Exception) as error:
        base_pruebas.ejecutar(base, insertar_entrada, (compra_id, funcion_con_butacas["id"], butaca))
    assert error.value.args[0] == 1062


# --- funciones superpuestas ---
def _crear_funcion(cliente, admin, pelicula_id, fecha_hora, sala_id=1):
    return cliente.post("/api/admin/funciones", headers=admin, json={
        "pelicula_id": pelicula_id, "sala_id": sala_id, "fecha_hora": fecha_hora, "precio": 5000,
    })


@pytest.mark.parametrize("fecha_hora, sala_id, status", [
    ("2031-07-01T19:00:00", 1, 409),  # empieza en medio de la existente
    ("2031-07-01T20:14:00", 1, 409),  # un minuto antes de que termine la limpieza (18:00 + 120 + 15)
    ("2031-07-01T15:46:00", 1, 409),  # termina (con limpieza) un minuto después de que empieza la existente
    ("2031-07-01T20:15:00", 1, 201),  # justo al terminar la limpieza
    ("2031-07-01T15:45:00", 1, 201),  # termina justo cuando empieza la existente
    ("2031-07-01T19:00:00", 2, 201),  # mismo horario en otra sala
])
def test_funciones_superpuestas_en_la_misma_sala_se_rechazan(
        cliente_http, admin, fabrica_funciones, fecha_hora, sala_id, status):
    pelicula_id = fabrica_funciones["pelicula_id"]  # dura 120 minutos
    assert _crear_funcion(cliente_http, admin, pelicula_id, "2031-07-01T18:00:00").status_code == 201

    respuesta = _crear_funcion(cliente_http, admin, pelicula_id, fecha_hora, sala_id)
    assert respuesta.status_code == status, respuesta.get_json()
    if status == 409:
        assert _codigo(respuesta) == "FUNCION_SUPERPUESTA"


def test_mover_una_funcion_encima_de_otra_tambien_se_rechaza(cliente_http, admin, fabrica_funciones):
    pelicula_id = fabrica_funciones["pelicula_id"]
    _crear_funcion(cliente_http, admin, pelicula_id, "2031-07-01T18:00:00")
    otra = _crear_funcion(cliente_http, admin, pelicula_id, "2031-07-01T21:00:00").get_json()
    respuesta = cliente_http.put(f"/api/admin/funciones/{otra['id']}", headers=admin,
                                 json={"fecha_hora": "2031-07-01T19:30:00"})
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "FUNCION_SUPERPUESTA"


# --- cancelación ---
def _a_horas_de_hoy(app, minutos_extra):
    """Fecha de función que queda HORAS_LIMITE_CANCELACION horas (más `minutos_extra`) después de ahora."""
    horas = app.config["HORAS_LIMITE_CANCELACION"]
    return (datetime.now() + timedelta(hours=horas, minutes=minutos_extra)).replace(microsecond=0)


def test_cancelar_justo_antes_del_plazo_libera_la_butaca_y_se_vuelve_a_vender(
        app_mysql, cliente_http, fabrica_funciones, ana, juan, base):
    funcion = fabrica_funciones["crear"](_a_horas_de_hoy(app_mysql, minutos_extra=3))
    butaca = funcion["butaca_ids"][0]
    compra_id = _comprar(cliente_http, funcion, ana, [butaca])

    respuesta = cliente_http.post(f"/api/compras/{compra_id}/cancelar", headers=ana)
    assert respuesta.status_code == 200, respuesta.get_json()
    assert _entradas_activas(base, funcion["id"], butaca) == 0
    assert _reservar(cliente_http, funcion, juan, [butaca]).status_code == 201
    assert _entradas_activas(base, funcion["id"], butaca) == 1


def test_cancelar_justo_despues_del_plazo_devuelve_409_y_la_butaca_sigue_vendida(
        app_mysql, cliente_http, fabrica_funciones, ana, juan, base):
    funcion = fabrica_funciones["crear"](_a_horas_de_hoy(app_mysql, minutos_extra=-3))
    butaca = funcion["butaca_ids"][0]
    compra_id = _comprar(cliente_http, funcion, ana, [butaca])

    respuesta = cliente_http.post(f"/api/compras/{compra_id}/cancelar", headers=ana)
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "FUERA_DE_PLAZO"
    assert _entradas_activas(base, funcion["id"], butaca) == 1
    assert _reservar(cliente_http, funcion, juan, [butaca]).status_code == 409


def test_cancelar_dos_veces_devuelve_409_ya_cancelada(cliente_http, funcion_con_butacas, ana):
    compra_id = _comprar(cliente_http, funcion_con_butacas, ana, funcion_con_butacas["butaca_ids"][:1])
    assert cliente_http.post(f"/api/compras/{compra_id}/cancelar", headers=ana).status_code == 200
    respuesta = cliente_http.post(f"/api/compras/{compra_id}/cancelar", headers=ana)
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "YA_CANCELADA"


# --- QR de ingreso ---
@pytest.fixture
def funcion_de_hoy(fabrica_funciones):
    """Función que empieza en 10 minutos (todavía se puede comprar y el QR es de hoy)."""
    inicio = (datetime.now() + timedelta(minutes=10)).replace(microsecond=0)
    if inicio.date() != datetime.now().date():
        pytest.skip("Faltan menos de 10 minutos para la medianoche: no hay una función de hoy que se pueda comprar.")
    return fabrica_funciones["crear"](inicio)


def _validar(cliente, admin, token_qr, funcion_id):
    return cliente.post(VALIDAR_QR, headers=admin, json={"token_qr": token_qr, "funcion_id": funcion_id})


def test_qr_valido_entra_y_el_segundo_uso_devuelve_ya_utilizada(cliente_http, funcion_de_hoy, ana, admin, base):
    compra_id = _comprar(cliente_http, funcion_de_hoy, ana, funcion_de_hoy["butaca_ids"][:2])
    token = _token_qr(base, compra_id)

    primera = _validar(cliente_http, admin, token, funcion_de_hoy["id"])
    assert primera.status_code == 200, primera.get_json()
    assert primera.get_json()["valido"] is True
    assert base_pruebas.filas(base, "SELECT utilizada_en FROM compras WHERE id = %s", (compra_id,))[0]["utilizada_en"]

    segunda = _validar(cliente_http, admin, token, funcion_de_hoy["id"])
    assert segunda.status_code == 409
    assert _codigo(segunda) == "YA_UTILIZADA"


def test_qr_de_otra_funcion_se_rechaza_y_no_se_marca_usado(
        cliente_http, fabrica_funciones, funcion_de_hoy, ana, admin, base):
    otra = fabrica_funciones["crear"](datetime(2031, 6, 11, 21, 0))
    compra_id = _comprar(cliente_http, funcion_de_hoy, ana, funcion_de_hoy["butaca_ids"][:1])

    respuesta = _validar(cliente_http, admin, _token_qr(base, compra_id), otra["id"])
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "OTRA_FUNCION"
    assert base_pruebas.filas(base, "SELECT utilizada_en FROM compras WHERE id = %s", (compra_id,))[0][
        "utilizada_en"] is None


def test_qr_alterado_se_rechaza_y_el_original_sigue_valiendo(cliente_http, funcion_de_hoy, ana, admin, base):
    compra_id = _comprar(cliente_http, funcion_de_hoy, ana, funcion_de_hoy["butaca_ids"][:1])
    token = _token_qr(base, compra_id)
    alterado = token[:-1] + ("A" if token[-1] != "A" else "B")

    respuesta = _validar(cliente_http, admin, alterado, funcion_de_hoy["id"])
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "QR_INVALIDO"
    assert _validar(cliente_http, admin, token, funcion_de_hoy["id"]).status_code == 200


def test_qr_de_una_compra_cancelada_devuelve_cancelada(cliente_http, funcion_con_butacas, ana, admin, base):
    compra_id = _comprar(cliente_http, funcion_con_butacas, ana, funcion_con_butacas["butaca_ids"][:1])
    token = _token_qr(base, compra_id)
    assert cliente_http.post(f"/api/compras/{compra_id}/cancelar", headers=ana).status_code == 200

    respuesta = _validar(cliente_http, admin, token, funcion_con_butacas["id"])
    assert respuesta.status_code == 409
    assert _codigo(respuesta) == "CANCELADA"


def test_cada_intento_de_validacion_queda_registrado(cliente_http, funcion_de_hoy, ana, admin, base):
    compra_id = _comprar(cliente_http, funcion_de_hoy, ana, funcion_de_hoy["butaca_ids"][:1])
    token = _token_qr(base, compra_id)
    _validar(cliente_http, admin, token, funcion_de_hoy["id"])
    _validar(cliente_http, admin, token, funcion_de_hoy["id"])

    resultados = base_pruebas.filas(
        base, "SELECT resultado FROM validaciones_ingreso WHERE compra_id = %s ORDER BY id", (compra_id,))
    assert [fila["resultado"] for fila in resultados] == ["valida", "ya_utilizada"]
