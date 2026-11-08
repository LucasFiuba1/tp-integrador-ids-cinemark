"""Pruebas de POST /api/admin/ingresos/validar y GET /api/admin/ingresos (SCRUM-73, SCRUM-125)."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Barrier, Lock, Thread
from unittest.mock import Mock, patch

import pytest
from flask import render_template

from src.backend.tokens import firmar_cancelacion, firmar_qr
from src.tests.utilidades import afirmar_error_json, crear_app_backend, simular_bd

RUTA = "/api/admin/ingresos/validar"
RUTA_HISTORIAL = "/api/admin/ingresos"
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


def _ultimo_insert_validacion(cursor):
    llamadas = [
        llamada.args for llamada in cursor.execute.call_args_list if "INSERT INTO validaciones_ingreso" in llamada.args[0]
    ]
    assert len(llamadas) == 1, f"Se esperaba un único INSERT en validaciones_ingreso y hubo {len(llamadas)}."
    return llamadas[0][1]


@pytest.fixture
def token_valido(app_backend):
    return firmar_qr(COMPRA_ID)


@pytest.fixture
def bd(token_valido):
    with simular_bd(destinos=("src.backend.services.ingresos",)) as simulacion:
        simulacion.cursor.fetchone.return_value = _fila_compra(token_valido)
        simulacion.cursor.fetchall.return_value = [{"fila": "D", "numero": 5}, {"fila": "D", "numero": 6}]
        yield simulacion


# --- permisos y formato de entrada (POST /validar) ---
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


# --- 1. QR_INVALIDO (se evalúa primero y persiste el rechazo) ---
@pytest.mark.parametrize("token_malo", ["token-falso", "eyJjb21wcmFfaWQiOjg4fQ.firma-invalida"])
def test_validar_firma_invalida_devuelve_409_qr_invalido_y_registra_intento(
    cliente_backend, cabeceras_admin, bd, token_malo
):
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_malo, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")
    assert _ultimo_insert_validacion(bd.cursor) == (None, FUNCION_ID, "qr_invalido")


def test_validar_token_de_cancelacion_no_sirve_como_qr(cliente_backend, cabeceras_admin, bd):
    token_cancelar = firmar_cancelacion(COMPRA_ID)
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_cancelar, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")
    assert _ultimo_insert_validacion(bd.cursor) == (None, FUNCION_ID, "qr_invalido")


def test_validar_compra_inexistente_o_con_otro_token_guardado_devuelve_qr_invalido(
    cliente_backend, cabeceras_admin, bd, token_valido
):
    bd.cursor.fetchone.return_value = None
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")
    assert _ultimo_insert_validacion(bd.cursor) == (None, FUNCION_ID, "qr_invalido")

    bd.cursor.execute.reset_mock()
    bd.cursor.fetchone.return_value = _fila_compra("otro-token-distinto")
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")
    assert _ultimo_insert_validacion(bd.cursor) == (None, FUNCION_ID, "qr_invalido")


@pytest.mark.parametrize("estado", ["pendiente", "vencida"])
def test_validar_compra_no_confirmada_ni_cancelada_devuelve_qr_invalido(
    cliente_backend, cabeceras_admin, bd, token_valido, estado
):
    bd.cursor.fetchone.return_value = _fila_compra(token_valido, estado=estado)
    respuesta = cliente_backend.post(
        RUTA, json={"token_qr": token_valido, "funcion_id": FUNCION_ID}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "QR_INVALIDO")
    assert _ultimo_insert_validacion(bd.cursor) == (COMPRA_ID, FUNCION_ID, "qr_invalido")


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
    assert _ultimo_insert_validacion(bd.cursor) == (COMPRA_ID, FUNCION_ID, "cancelada")


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
    assert _ultimo_insert_validacion(bd.cursor) == (COMPRA_ID, FUNCION_ID, "ya_utilizada")


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
    assert _ultimo_insert_validacion(bd.cursor) == (COMPRA_ID, FUNCION_ID, "otra_funcion")


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
    assert _ultimo_insert_validacion(bd.cursor) == (COMPRA_ID, FUNCION_ID, "fuera_de_fecha")


# --- 6. Caso válido y concurrencia ---
def test_validar_qr_valido_bloquea_fila_marca_utilizada_en_registra_y_devuelve_detalle(
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
    assert _ultimo_insert_validacion(bd.cursor) == (COMPRA_ID, FUNCION_ID, "valida")


def test_doble_escaneo_simultaneo_solo_admite_el_primero_y_rechaza_el_segundo_con_ya_utilizada(
    cabeceras_admin, token_valido
):
    """Dos hilos escanean el mismo QR al mismo tiempo: el bloqueo de fila (FOR UPDATE) serializa la transacción."""
    app = crear_app_backend()
    candado_fila = Lock()
    barrera = Barrier(2)
    estado_fila = _fila_compra(token_valido)
    validaciones_registradas = []

    @contextmanager
    def transaccion_con_bloqueo_de_fila():
        with candado_fila:
            cursor = Mock()

            def ejecutar_sql(sql, parametros=()):
                if "UPDATE compras SET utilizada_en = NOW()" in sql:
                    estado_fila["utilizada_en"] = datetime(2026, 11, 10, 20, 25)
                elif "INSERT INTO validaciones_ingreso" in sql:
                    validaciones_registradas.append(parametros)

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
    assert validaciones_registradas == [
        (COMPRA_ID, FUNCION_ID, "valida"),
        (COMPRA_ID, FUNCION_ID, "ya_utilizada"),
    ]


# --- 7. Historial de validaciones (GET /api/admin/ingresos, SCRUM-125) ---
def test_historial_sin_token_devuelve_401(cliente_backend):
    afirmar_error_json(cliente_backend.get(RUTA_HISTORIAL), 401, "NO_AUTENTICADO")


def test_historial_con_rol_cliente_devuelve_403(cliente_backend, cabeceras_cliente):
    afirmar_error_json(cliente_backend.get(RUTA_HISTORIAL, headers=cabeceras_cliente), 403, "SIN_PERMISO")


@pytest.mark.parametrize(
    "query",
    [
        {"funcion_id": ""},
        {"funcion_id": "0"},
        {"funcion_id": "-1"},
        {"funcion_id": "abc"},
        {"limite": ""},
        {"limite": "0"},
        {"limite": "-5"},
        {"limite": "101"},
        {"limite": "abc"},
    ],
)
def test_historial_con_parametros_invalidos_devuelve_400(cliente_backend, cabeceras_admin, bd, query):
    respuesta = cliente_backend.get(RUTA_HISTORIAL, query_string=query, headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")
    bd.consultar.assert_not_called()


def test_historial_sin_filtros_usa_limite_20_y_ordena_por_fecha_descendente(cliente_backend, cabeceras_admin, bd):
    bd.consultar.return_value = [
        {
            "id": 2,
            "compra_id": 88,
            "funcion_id": 12,
            "resultado": "valida",
            "fecha_hora": datetime(2026, 11, 10, 20, 21),
            "pelicula": "Volver al futuro",
            "butacas": "D5, D6",
        },
        {
            "id": 1,
            "compra_id": None,
            "funcion_id": None,
            "resultado": "qr_invalido",
            "fecha_hora": datetime(2026, 11, 10, 20, 19),
            "pelicula": None,
            "butacas": None,
        },
    ]
    respuesta = cliente_backend.get(RUTA_HISTORIAL, headers=cabeceras_admin)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [
        {
            "id": 2,
            "compra_id": 88,
            "funcion_id": 12,
            "hora": "2026-11-10T20:21:00",
            "pelicula": "Volver al futuro",
            "butacas": "D5, D6",
            "resultado": "valida",
        },
        {
            "id": 1,
            "compra_id": None,
            "funcion_id": None,
            "hora": "2026-11-10T20:19:00",
            "pelicula": "—",
            "butacas": "—",
            "resultado": "qr_invalido",
        },
    ]
    sql, parametros = bd.consultar.call_args.args
    assert "WHERE v.funcion_id = %s" not in sql
    assert "ORDER BY v.fecha_hora DESC, v.id DESC LIMIT %s" in sql
    assert parametros == (20,)


def test_historial_con_funcion_id_y_limite_filtra_por_ambos(cliente_backend, cabeceras_admin, bd):
    bd.consultar.return_value = []
    respuesta = cliente_backend.get(
        RUTA_HISTORIAL, query_string={"funcion_id": "12", "limite": "5"}, headers=cabeceras_admin
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json() == []
    sql, parametros = bd.consultar.call_args.args
    assert "WHERE v.funcion_id = %s" in sql
    assert parametros == (12, 5)


def test_template_validar_renderiza_los_registros_del_endpoint(
    app_frontend, cliente_backend, cabeceras_admin, bd
):
    """CA 5 de SCRUM-125: verifica que backoffice/validar.html renderice todos los estados devueltos por el endpoint."""
    bd.consultar.return_value = [
        {
            "id": 6, "compra_id": 88, "funcion_id": 12, "resultado": "valida",
            "fecha_hora": datetime(2026, 11, 10, 20, 21), "pelicula": "Volver al futuro", "butacas": "D5, D6",
        },
        {
            "id": 5, "compra_id": 88, "funcion_id": 12, "resultado": "ya_utilizada",
            "fecha_hora": datetime(2026, 11, 10, 20, 22), "pelicula": "Volver al futuro", "butacas": "D5, D6",
        },
        {
            "id": 4, "compra_id": 89, "funcion_id": 12, "resultado": "cancelada",
            "fecha_hora": datetime(2026, 11, 10, 20, 20), "pelicula": "Volver al futuro", "butacas": "C2",
        },
        {
            "id": 3, "compra_id": None, "funcion_id": 12, "resultado": "qr_invalido",
            "fecha_hora": datetime(2026, 11, 10, 20, 18), "pelicula": None, "butacas": None,
        },
        {
            "id": 2, "compra_id": 90, "funcion_id": 12, "resultado": "otra_funcion",
            "fecha_hora": datetime(2026, 11, 10, 20, 15), "pelicula": "Código Medianoche", "butacas": "B3",
        },
        {
            "id": 1, "compra_id": 91, "funcion_id": 12, "resultado": "fuera_de_fecha",
            "fecha_hora": datetime(2026, 11, 10, 20, 10), "pelicula": "Pequeños gigantes", "butacas": "F7",
        },
    ]
    historial = cliente_backend.get(RUTA_HISTORIAL, headers=cabeceras_admin).get_json()
    with app_frontend.test_request_context("/admin/validar"):
        html = render_template(
            "backoffice/validar.html",
            seccion="validar",
            formulario={"codigo": ""},
            errores={},
            resultado=None,
            historial=historial,
        )
    for badge in (
        'badge-valida">Válida</span>',
        'badge-ya_utilizada">Ya usada</span>',
        'badge-cancelada">Cancelada</span>',
        'badge-qr_invalido">Inválida</span>',
        'badge-otra_funcion">Otra función</span>',
        'badge-fuera_de_fecha">Fuera de fecha</span>',
    ):
        assert badge in html
    assert "D5, D6" in html and "Volver al futuro" in html
