"""Pruebas de POST /api/admin/ingresos/validar (SCRUM-73)."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Barrier, Lock, Thread
from unittest.mock import Mock, patch

import pytest

from src.backend.tokens import firmar_cancelacion, firmar_qr
from src.tests.utilidades import afirmar_error_json, crear_app_backend, simular_bd

RUTA = "/api/admin/ingresos/validar"
COMPRA_ID = 88
FUNCION_ID = 12


def _ahora_redondeado():
    return datetime.now().replace(microsecond=0)


def _fila_compra(token_qr, **cambios):
    ahora = _ahora_redondeado()
    fila = {
        "id": COMPRA_ID,
        "funcion_id": FUNCION_ID,
        "estado": "confirmada",
        "token_qr": token_qr,
        "utilizada_en": None,
        "fecha_hora": ahora + timedelta(minutes=15),
        "funcion_activa": 1,
        "pelicula": "Volver al futuro",
        "duracion_min": 116,
        "sala": "Sala 1",
        "local": "Paradiso Centro",
        "titular": "Ana Pérez",
    }
    fila.update(cambios)
    return fila


@pytest.fixture
def token_valido(app_backend):
    return firmar_qr(COMPRA_ID)


@pytest.fixture
def bd(token_valido):
    with simular_bd(destinos=("src.backend.services.ingresos",)) as simulacion:
        simulacion.cursor.fetchone.return_value = _fila_compra(token_valido)
        simulacion.cursor.fetchall.return_value = [{"fila": "D", "numero": 5}, {"fila": "D", "numero": 6}]
        yield simulacion


# --- permisos y formato de entrada ---
def test_validar_sin_token_devuelve_401(cliente_backend, token_valido):
    respuesta = cliente_backend.post(RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID})
    afirmar_error_json(respuesta, 401, "NO_AUTENTICADO")


def test_validar_con_rol_cliente_devuelve_403(cliente_backend, cabeceras_cliente, token_valido):
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_cliente
    )
    afirmar_error_json(respuesta, 403, "SIN_PERMISO")


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"token_qr": "abc"},
        {"funcion_id": 12},
        {"token_qr": "", "funcion_id": 12},
        {"token_qr": "   ", "funcion_id": 12},
        {"token_qr": 123, "funcion_id": 12},
        {"token_qr": "a" * 256, "funcion_id": 12},
        {"token_qr": "abc", "funcion_id": 0},
        {"token_qr": "abc", "funcion_id": -1},
        {"token_qr": "abc", "funcion_id": "12"},
        {"token_qr": "abc", "funcion_id": True},
    ],
)
def test_validar_con_datos_invalidos_devuelve_400(cliente_backend, cabeceras_admin, bd, cuerpo):
    respuesta = cliente_backend.post(RUTA, json=cuerpo, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    bd.cursor.execute.assert_not_called()


# --- 1. QR_INVALIDO (se evalúa primero) ---
@pytest.mark.parametrize("token_malo", ["token-falso", "eyJjb21wcmFfaWQiOjg4fQ.firma-invalida"])
def test_validar_firma_invalida_devuelve_409_qr_invalido_sin_tocar_la_base(
    cliente_backend, cabeceras_admin, bd, token_malo
):
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_malo, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")
    bd.cursor.execute.assert_not_called()


def test_validar_token_de_cancelacion_no_sirve_como_qr(cliente_backend, cabeceras_admin, bd):
    token_cancelar = firmar_cancelacion(COMPRA_ID)
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_cancelar, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")


def test_validar_compra_inexistente_o_con_otro_token_guardado_devuelve_qr_invalido(
    cliente_backend, cabeceras_admin, bd, token_valido
):
    bd.cursor.fetchone.return_value = None
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")

    bd.cursor.fetchone.return_value = _fila_compra("otro-token-distinto")
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")


@pytest.mark.parametrize("estado", ["pendiente", "vencida"])
def test_validar_compra_no_confirmada_ni_cancelada_devuelve_qr_invalido(
    cliente_backend, cabeceras_admin, bd, token_valido, estado
):
    bd.cursor.fetchone.return_value = _fila_compra(token_valido, estado=estado)
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")


# --- 2. CANCELADA (prioridad sobre YA_UTILIZADA, OTRA_FUNCION y FUERA_DE_FECHA) ---
def test_validar_compra_cancelada_devuelve_409_cancelada_antes_que_otros_motivos(
    cliente_backend, cabeceras_admin, bd, token_valido
):
    bd.cursor.fetchone.return_value = _fila_compra(
        token_valido,
        estado="cancelada",
        utilizada_en=datetime(2026, 11, 10, 20, 21),
        funcion_id=999,
        fecha_hora=datetime(2020, 1, 1, 20, 0),
    )
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "CANCELADA")


# --- 3. YA_UTILIZADA (incluye fecha y hora del primer uso; prioridad sobre OTRA_FUNCION y FUERA_DE_FECHA) ---
def test_validar_entrada_ya_usada_devuelve_409_con_fecha_y_hora_del_primer_uso(
    cliente_backend, cabeceras_admin, bd, token_valido
):
    bd.cursor.fetchone.return_value = _fila_compra(
        token_valido,
        utilizada_en=datetime(2026, 11, 10, 20, 21),
        funcion_id=999,
        fecha_hora=datetime(2020, 1, 1, 20, 0),
    )
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "YA_UTILIZADA", "Este QR ya se usó el 10/11 a las 20:21.")


# --- 4. OTRA_FUNCION (prioridad sobre FUERA_DE_FECHA) ---
def test_validar_funcion_distinta_devuelve_409_otra_funcion_antes_que_fuera_de_fecha(
    cliente_backend, cabeceras_admin, bd, token_valido
):
    bd.cursor.fetchone.return_value = _fila_compra(
        token_valido, funcion_id=99, fecha_hora=datetime(2020, 1, 1, 20, 0)
    )
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "OTRA_FUNCION")


# --- 5. FUERA_DE_FECHA (otro día, función ya terminada o función dada de baja) ---
@pytest.mark.parametrize(
    "cambios",
    [
        {"fecha_hora": datetime.now() + timedelta(days=1)},
        {"fecha_hora": datetime.now() - timedelta(days=1)},
        {"fecha_hora": datetime.now() - timedelta(minutes=120), "duracion_min": 100},
        {"funcion_activa": 0},
    ],
)
def test_validar_funcion_fuera_de_fecha_o_finalizada_devuelve_409(
    cliente_backend, cabeceras_admin, bd, token_valido, cambios
):
    bd.cursor.fetchone.return_value = _fila_compra(token_valido, **cambios)
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "FUERA_DE_FECHA")


# --- 6. Caso válido y concurrencia ---
def test_validar_qr_valido_bloquea_fila_marca_utilizada_en_y_devuelve_detalle(
    cliente_backend, cabeceras_admin, bd, token_valido
):
    fila = _fila_compra(token_valido)
    bd.cursor.fetchone.return_value = fila
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "valido": True,
        "compra_id": COMPRA_ID,
        "butacas": ["D5", "D6"],
        "pelicula": "Volver al futuro",
        "funcion": fila["fecha_hora"].isoformat(),
        "local": "Paradiso Centro",
        "sala": "Sala 1",
        "titular": "Ana Pérez",
    }

    sentencias = [llamada.args[0] for llamada in bd.cursor.execute.call_args_list]
    assert "FOR UPDATE" in sentencias[0]
    assert any("UPDATE compras SET utilizada_en = NOW() WHERE id = %s" in sql for sql in sentencias)


def test_doble_escaneo_simultaneo_solo_admite_el_primero_y_rechaza_el_segundo_con_ya_utilizada(
    cabeceras_admin, token_valido
):
    """Dos hilos escanean el mismo QR al mismo tiempo: el bloqueo de fila (FOR UPDATE) serializa la transacción."""
    app = crear_app_backend()
    candado_fila = Lock()
    barrera = Barrier(2)
    estado_fila = _fila_compra(token_valido)

    @contextmanager
    def transaccion_con_bloqueo_de_fila():
        with candado_fila:
            cursor = Mock()

            def ejecutar_sql(sql, parametros=()):
                if "UPDATE compras SET utilizada_en = NOW()" in sql:
                    estado_fila["utilizada_en"] = datetime(2026, 11, 10, 20, 25)

            cursor.execute.side_effect = ejecutar_sql
            cursor.fetchone.side_effect = lambda: dict(estado_fila)
            cursor.fetchall.return_value = [{"fila": "D", "numero": 5}]
            yield cursor

    respuestas = []

    def escanear():
        barrera.wait()
        with app.test_client() as cliente:
            respuestas.append(
                cliente.post(
                    RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
                )
            )

    with patch("src.backend.services.ingresos.transaccion", side_effect=transaccion_con_bloqueo_de_fila):
        hilos = [Thread(target=escanear), Thread(target=escanear)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

    codigos = sorted(r.status_code for r in respuestas)
    assert codigos == [200, 409]
    rechazo = next(r for r in respuestas if r.status_code == 409)
    afirmar_error_json(rechazo, 409, "YA_UTILIZADA", "Este QR ya se usó el 10/11 a las 20:25.")
