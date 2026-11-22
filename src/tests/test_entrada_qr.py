"""Pruebas de la entrada del QR (SCRUM-74): GET /api/compras/por-qr y la pantalla /entrada.

Cualquiera que escanee el QR ve los datos básicos de la entrada; el comprador ve su compra completa; el admin ve lo
mismo más el titular y puede validar el ingreso. Qué ve cada uno lo decide el backend.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.backend.tokens import firmar_cancelacion, firmar_qr
from src.tests.utilidades import ID_CLIENTE, afirmar_error_json, simular_bd

COMPRA_ID = 88
RUTA = "/api/compras/por-qr"
CAMPOS_BASICOS = {"vista", "estado", "pelicula", "poster_url", "local", "sala", "funcion", "butacas"}
FUNCION_FUTURA = datetime(2099, 11, 30, 20, 30)


def _fila_detalle(**cambios):
    fila = {
        "id": COMPRA_ID, "usuario_id": ID_CLIENTE, "funcion_id": 12, "estado": "confirmada",
        "total": Decimal("16500.00"), "vence_en": datetime(2026, 11, 5, 18, 40), "cancelada_en": None,
        "utilizada_en": None, "token_qr": "token-qr", "vencida": 1, "fecha_hora": FUNCION_FUTURA,
        "titulo": "Volver al futuro", "poster_url": None, "sala": "Sala 1", "local": "Paradiso Centro",
        "email": "ana@email.com",
    }
    fila.update(cambios)
    return fila


def _fila_compra(**cambios):
    fila = {"usuario_id": ID_CLIENTE, "estado": "confirmada", "nombre": "Ana María García",
            "fecha_hora": FUNCION_FUTURA, "duracion_min": 116}
    fila.update(cambios)
    return fila


@contextmanager
def base_con_compra(detalle=None, compra=None):
    """Base simulada para obtener_por_qr: detalle de la compra, entradas, servicios y datos de comprador/función."""
    with simular_bd(destinos=("src.backend.services.compras",)) as simulacion:
        simulacion.consultar_uno.side_effect = [detalle or _fila_detalle(), compra or _fila_compra()]
        simulacion.consultar.side_effect = [
            [{"id": 41, "fila": "D", "numero": 5, "precio": Decimal("5000.00")},
             {"id": 42, "fila": "D", "numero": 6, "precio": Decimal("5000.00")}],
            [{"servicio_id": 1, "nombre": "Combo pochoclos", "cantidad": 1, "precio_unitario": Decimal("6500.00")}],
        ]
        yield simulacion


@pytest.fixture
def bd():
    with base_con_compra() as simulacion:
        yield simulacion


@pytest.fixture
def token_qr(app_backend):
    return firmar_qr(COMPRA_ID)


def _pedir(cliente, token, cabeceras=None):
    return cliente.get(RUTA, query_string={"token": token}, headers=cabeceras or {})


# --- API: qué ve cada uno ---
def test_anonimo_ve_solo_los_datos_basicos_de_la_entrada(cliente_backend, bd, token_qr):
    respuesta = _pedir(cliente_backend, token_qr)
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert set(datos) == CAMPOS_BASICOS
    assert datos["vista"] == "publica"
    assert datos["pelicula"] == "Volver al futuro"
    assert datos["funcion"] == "2099-11-30T20:30:00"
    assert datos["butacas"] == ["D5", "D6"]
    assert datos["estado"] == "valida"


def test_cliente_que_no_hizo_la_compra_ve_lo_mismo_que_un_anonimo(cliente_backend, cabeceras_cliente, token_qr):
    with base_con_compra(compra=_fila_compra(usuario_id=999)):
        datos = _pedir(cliente_backend, token_qr, cabeceras_cliente).get_json()
    assert set(datos) == CAMPOS_BASICOS
    assert datos["vista"] == "publica"


def test_comprador_ve_su_compra_completa_sin_datos_de_otros(cliente_backend, bd, cabeceras_cliente, token_qr):
    datos = _pedir(cliente_backend, token_qr, cabeceras_cliente).get_json()
    assert datos["vista"] == "comprador"
    assert datos["id"] == COMPRA_ID
    assert datos["cantidad_entradas"] == 2
    assert datos["servicios"][0]["nombre"] == "Combo pochoclos"
    assert datos["total"] == 16500.0
    assert datos["estado_pago"] == "pagado"
    assert "titular" not in datos


def test_admin_ve_la_compra_completa_y_el_titular(cliente_backend, bd, cabeceras_admin, token_qr):
    datos = _pedir(cliente_backend, token_qr, cabeceras_admin).get_json()
    assert datos["vista"] == "admin"
    assert datos["titular"] == "Ana María García"
    assert datos["id"] == COMPRA_ID


@pytest.mark.parametrize("cabeceras", [{}, {"Authorization": "Bearer token-roto"}, {"Authorization": "Basic x"}])
def test_token_de_sesion_ausente_o_invalido_se_trata_como_anonimo(cliente_backend, bd, token_qr, cabeceras):
    respuesta = _pedir(cliente_backend, token_qr, cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["vista"] == "publica"


@pytest.mark.parametrize("vista_cabeceras", [None, "cabeceras_cliente", "cabeceras_admin"])
def test_ninguna_vista_expone_email_qr_ni_datos_para_cancelar(cliente_backend, bd, token_qr, request, vista_cabeceras):
    cabeceras = request.getfixturevalue(vista_cabeceras) if vista_cabeceras else None
    datos = _pedir(cliente_backend, token_qr, cabeceras).get_json()
    for campo in ("email", "qr_png_base64", "cancelable", "cancelable_hasta", "butaca_ids", "usuario_id"):
        assert campo not in datos


# --- API: estado de la entrada ---
@pytest.mark.parametrize("detalle, compra, estado", [
    ({}, {}, "valida"),
    ({"utilizada_en": datetime(2099, 11, 30, 20, 10)}, {}, "utilizada"),
    ({"estado": "cancelada", "token_qr": None, "cancelada_en": datetime(2026, 11, 20, 10, 0)},
     {"estado": "cancelada"}, "cancelada"),
    ({"estado": "pendiente"}, {"estado": "pendiente"}, "pendiente"),
    ({}, {"fecha_hora": datetime.now() - timedelta(hours=3), "duracion_min": 120}, "vencida"),
])
def test_estado_de_la_entrada(cliente_backend, token_qr, detalle, compra, estado):
    with base_con_compra(_fila_detalle(**detalle), _fila_compra(**compra)):
        assert _pedir(cliente_backend, token_qr).get_json()["estado"] == estado


def test_entrada_de_una_funcion_que_sigue_en_curso_todavia_es_valida(cliente_backend, token_qr):
    compra = _fila_compra(fecha_hora=datetime.now() - timedelta(minutes=30), duracion_min=120)
    with base_con_compra(compra=compra):
        assert _pedir(cliente_backend, token_qr).get_json()["estado"] == "valida"


def test_comprador_de_una_compra_cancelada_ve_el_pago_anulado(cliente_backend, cabeceras_cliente, token_qr):
    with base_con_compra(_fila_detalle(estado="cancelada"), _fila_compra(estado="cancelada")):
        assert _pedir(cliente_backend, token_qr, cabeceras_cliente).get_json()["estado_pago"] == "anulado"


# --- API: errores ---
@pytest.mark.parametrize("token", ["", "token-invalido", None])
def test_por_qr_con_token_invalido_devuelve_400(cliente_backend, bd, token):
    query = {"token": token} if token is not None else {}
    afirmar_error_json(cliente_backend.get(RUTA, query_string=query), 400, "TOKEN_INVALIDO")
    bd.consultar_uno.assert_not_called()


def test_por_qr_no_acepta_el_token_de_cancelacion(cliente_backend, bd):
    afirmar_error_json(_pedir(cliente_backend, firmar_cancelacion(COMPRA_ID)), 400, "TOKEN_INVALIDO")


def test_por_qr_de_compra_inexistente_devuelve_404(cliente_backend, bd, token_qr):
    bd.consultar_uno.side_effect = [None]
    afirmar_error_json(_pedir(cliente_backend, token_qr), 404, "NO_ENCONTRADO")


# --- Pantalla: GET /entrada ---
ENTRADA_PUBLICA = {
    "vista": "publica", "estado": "valida", "pelicula": "Volver al futuro", "poster_url": None,
    "local": "Paradiso Centro", "sala": "Sala 1", "funcion": "2099-11-30T20:30:00", "butacas": ["D5", "D6"],
}
ENTRADA_COMPRADOR = {
    **ENTRADA_PUBLICA, "vista": "comprador", "id": COMPRA_ID, "cantidad_entradas": 2, "total": 16500.0,
    "servicios": [{"nombre": "Combo pochoclos", "cantidad": 1}], "estado_pago": "pagado",
    "utilizada_en": None, "cancelada_en": None,
}
ENTRADA_ADMIN = {**ENTRADA_COMPRADOR, "vista": "admin", "titular": "Ana María García"}
FUNCIONES_HOY = [{"valor": "", "texto": "Elegí la función"}, {"valor": 12, "texto": "20:30 · Volver al futuro"}]
FORMULARIO = 'action="/admin/ingreso"'


@pytest.fixture
def respuesta_api():
    return {"datos": ENTRADA_PUBLICA, "error": None}


@pytest.fixture
def llamar(respuesta_api):
    with patch("src.frontend.routes.publico.llamar",
               side_effect=lambda *args, **kwargs: (respuesta_api["datos"], respuesta_api["error"])) as simulado, \
         patch("src.frontend.routes.publico.funciones_de_hoy", return_value=FUNCIONES_HOY):
        yield simulado


def _html(cliente, url="/entrada?token=abc.123"):
    return cliente.get(url).get_data(as_text=True)


def test_vista_publica_muestra_la_funcion_sin_datos_de_la_compra(cliente_frontend, llamar):
    respuesta = cliente_frontend.get("/entrada?token=abc.123")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Volver al futuro" in html and "D5, D6" in html and "Válida para ingresar" in html
    for privado in ("N.º de operación", "Total", "Combo pochoclos", "Titular", "Pago", FORMULARIO):
        assert privado not in html
    llamar.assert_called_once_with("GET", "/api/compras/por-qr", params={"token": "abc.123"})


def test_vista_comprador_muestra_su_compra_y_el_acceso_al_perfil(cliente_logueado, llamar, respuesta_api):
    respuesta_api["datos"] = ENTRADA_COMPRADOR
    html = _html(cliente_logueado)
    assert "Tu entrada" in html
    for dato in ("N.º de operación #88", "Combo pochoclos", "Pagado", "$16.500", 'href="/perfil"'):
        assert dato in html
    assert FORMULARIO not in html and "Titular" not in html


def test_vista_admin_ofrece_validar_con_el_token_y_la_funcion_recordada(cliente_admin, llamar, respuesta_api):
    respuesta_api["datos"] = ENTRADA_ADMIN
    with cliente_admin.session_transaction() as sesion:
        sesion["funcion_ingreso"] = 12
    html = _html(cliente_admin)
    assert "Ana María García" in html
    assert '<form method="post" action="/admin/ingreso"' in html
    assert '<input type="hidden" name="token" value="abc.123">' in html
    assert '<option value="12" selected>' in html


def test_ver_la_entrada_no_la_valida(cliente_admin, llamar, respuesta_api):
    respuesta_api["datos"] = ENTRADA_ADMIN
    _html(cliente_admin)
    assert [llamada.args[1] for llamada in llamar.call_args_list] == ["/api/compras/por-qr"]


@pytest.mark.parametrize("estado, texto", [
    ("utilizada", "ya se usó"), ("cancelada", "se canceló"), ("vencida", "ya terminó"), ("pendiente", "no está pagada"),
])
def test_entrada_no_valida_avisa_y_no_ofrece_validar_ni_al_admin(cliente_admin, llamar, respuesta_api, estado, texto):
    respuesta_api["datos"] = {**ENTRADA_ADMIN, "estado": estado}
    html = _html(cliente_admin)
    assert texto in html
    assert FORMULARIO not in html


def test_entrada_acepta_la_url_completa_del_qr_en_el_token(cliente_frontend, llamar):
    cliente_frontend.get("/entrada?token=" + "http://localhost:5001/entrada?token%3Dabc.123")
    llamar.assert_called_once_with("GET", "/api/compras/por-qr", params={"token": "abc.123"})


def test_entrada_sin_token_no_llama_a_la_api(cliente_frontend, llamar):
    respuesta = cliente_frontend.get("/entrada")
    assert respuesta.status_code == 400
    assert "Falta el código del QR." in respuesta.get_data(as_text=True)
    llamar.assert_not_called()


def test_entrada_con_token_invalido_muestra_el_error_de_la_api(cliente_frontend, llamar, respuesta_api):
    respuesta_api["datos"] = None
    respuesta_api["error"] = {"status": 400, "codigo": "TOKEN_INVALIDO", "mensaje": "El código QR no es válido."}
    respuesta = cliente_frontend.get("/entrada?token=roto")
    assert respuesta.status_code == 400
    assert "El código QR no es válido." in respuesta.get_data(as_text=True)
