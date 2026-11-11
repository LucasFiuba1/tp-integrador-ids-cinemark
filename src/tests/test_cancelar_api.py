"""Pruebas de los endpoints de detalle y cancelación de compras (SCRUM-69, SCRUM-70, SCRUM-123)."""
import base64
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.backend.services.qr import generar_qr
from src.backend.tokens import firmar_cancelacion, firmar_qr
from src.tests.utilidades import ID_CLIENTE, afirmar_error_json, simular_bd

COMPRA_ID = 88


def _fila_detalle(**cambios):
    fila = {
        "id": COMPRA_ID,
        "usuario_id": ID_CLIENTE,
        "estado": "confirmada",
        "total": Decimal("23000.00"),
        "vence_en": datetime(2026, 11, 5, 18, 40),
        "cancelada_en": None,
        "utilizada_en": None,
        "token_qr": "token-qr-de-prueba",
        "vencida": 1,
        "fecha_hora": datetime.now().replace(microsecond=0) + timedelta(days=2),
        "titulo": "Volver al futuro",
        "poster_url": None,
        "sala": "Sala 1",
        "local": "Paradiso Centro",
        "email": "ana@email.com",
    }
    fila.update(cambios)
    return fila


def _fila_cancelar(**cambios):
    fila = {
        "id": COMPRA_ID,
        "usuario_id": ID_CLIENTE,
        "estado": "confirmada",
        "utilizada_en": None,
        "fecha_hora": datetime.now().replace(microsecond=0) + timedelta(days=2),
    }
    fila.update(cambios)
    return fila


@pytest.fixture
def token_cancelacion(app_backend):
    return firmar_cancelacion(COMPRA_ID)


@pytest.fixture
def bd():
    with simular_bd(destinos=("src.backend.services.compras",)) as simulacion:
        simulacion.consultar_uno.return_value = _fila_detalle()
        simulacion.consultar.side_effect = [
            [{"fila": "D", "numero": 5, "precio": Decimal("5000.00")}, {"fila": "D", "numero": 6, "precio": Decimal("5000.00")}],
            [{"servicio_id": 1, "nombre": "Combo pochoclos grande", "cantidad": 2,
              "precio_unitario": Decimal("6500.00")}],
        ]
        simulacion.cursor.fetchone.return_value = _fila_cancelar()
        yield simulacion


# --- GET /api/compras/<id> ---
def test_obtener_compra_sin_token_devuelve_401(cliente_backend):
    afirmar_error_json(cliente_backend.get(f"/api/compras/{COMPRA_ID}"), 401, "NO_AUTENTICADO")


def test_obtener_compra_de_otro_usuario_como_admin_devuelve_el_detalle(cliente_backend, cabeceras_admin, bd):
    bd.consultar_uno.return_value = _fila_detalle(usuario_id=999)
    respuesta = cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_admin)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["id"] == COMPRA_ID


def test_obtener_compra_inexistente_devuelve_404(cliente_backend, cabeceras_cliente, bd):
    bd.consultar_uno.return_value = None
    afirmar_error_json(cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente), 404, "NO_ENCONTRADO")


def test_obtener_compra_ajena_devuelve_403(cliente_backend, cabeceras_cliente, bd):
    bd.consultar_uno.return_value = _fila_detalle(usuario_id=999)
    afirmar_error_json(cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente), 403, "SIN_PERMISO")


def test_obtener_compra_ok_devuelve_detalle_completo(cliente_backend, cabeceras_cliente, bd):
    respuesta = cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente)
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["id"] == COMPRA_ID
    assert datos["pelicula"] == "Volver al futuro"
    assert datos["butacas"] == ["D5", "D6"]
    assert datos["subtotal_entradas"] == 10000.0
    assert datos["servicios"] == [
        {"servicio_id": 1, "nombre": "Combo pochoclos grande", "cantidad": 2, "precio_unitario": 6500.0,
         "subtotal": 13000.0}
    ]
    assert datos["total"] == 23000.0
    assert datos["cancelable"] is True
    assert datos["funcion"] == _fila_detalle()["fecha_hora"].isoformat()
    assert datos["cancelable_hasta"] == (_fila_detalle()["fecha_hora"] - timedelta(hours=2)).isoformat()
    assert datos["vence_en"] is None


def test_obtener_compra_confirmada_incluye_el_qr_de_ingreso(cliente_backend, cabeceras_cliente, bd):
    datos = cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente).get_json()
    assert base64.b64decode(datos["qr_png_base64"]) == generar_qr("token-qr-de-prueba")


@pytest.mark.parametrize("estado", ["pendiente", "cancelada"])
def test_obtener_compra_no_confirmada_no_incluye_qr(cliente_backend, cabeceras_cliente, bd, estado):
    bd.consultar_uno.return_value = _fila_detalle(estado=estado, vencida=0, token_qr=None)
    datos = cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente).get_json()
    assert datos["qr_png_base64"] is None


def test_obtener_compra_pendiente_en_plazo_informa_vence_en(cliente_backend, cabeceras_cliente, bd):
    bd.consultar_uno.return_value = _fila_detalle(estado="pendiente", vencida=0, token_qr=None)
    datos = cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente).get_json()
    assert datos["estado"] == "pendiente"
    assert datos["vence_en"] == "2026-11-05T18:40:00"
    assert datos["cancelable"] is False


def test_obtener_compra_pendiente_vencida_se_informa_como_vencida(cliente_backend, cabeceras_cliente, bd):
    bd.consultar_uno.return_value = _fila_detalle(estado="pendiente", vencida=1, token_qr=None)
    datos = cliente_backend.get(f"/api/compras/{COMPRA_ID}", headers=cabeceras_cliente).get_json()
    assert datos["estado"] == "vencida"
    assert datos["vence_en"] is None
    assert datos["cancelable"] is False
    assert datos["qr_png_base64"] is None


# --- GET /api/compras/por-token (público) ---
def test_obtener_por_token_valido_no_pide_sesion_y_devuelve_detalle(cliente_backend, bd, token_cancelacion):
    respuesta = cliente_backend.get("/api/compras/por-token", query_string={"token": token_cancelacion})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["id"] == COMPRA_ID


@pytest.mark.parametrize("token", ["", "token-invalido", None])
def test_obtener_por_token_invalido_devuelve_400_token_invalido(cliente_backend, bd, token):
    query = {"token": token} if token is not None else {}
    afirmar_error_json(cliente_backend.get("/api/compras/por-token", query_string=query), 400, "TOKEN_INVALIDO")


def test_obtener_por_token_de_qr_no_sirve_para_cancelar(cliente_backend, bd):
    token_qr = firmar_qr(COMPRA_ID)
    afirmar_error_json(
        cliente_backend.get("/api/compras/por-token", query_string={"token": token_qr}), 400, "TOKEN_INVALIDO"
    )


# --- POST /api/compras/<id>/cancelar ---
def test_cancelar_sin_token_devuelve_401(cliente_backend):
    afirmar_error_json(cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar"), 401, "NO_AUTENTICADO")


def test_cancelar_compra_inexistente_devuelve_404(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = None
    afirmar_error_json(
        cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente), 404, "NO_ENCONTRADO"
    )


def test_cancelar_compra_ajena_devuelve_403(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_cancelar(usuario_id=999)
    afirmar_error_json(
        cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente), 403, "SIN_PERMISO"
    )


def test_cancelar_compra_ya_cancelada_devuelve_409(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_cancelar(estado="cancelada")
    afirmar_error_json(
        cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente), 409, "YA_CANCELADA"
    )


def test_cancelar_compra_ya_utilizada_devuelve_409(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_cancelar(utilizada_en=datetime(2026, 11, 10, 20, 21))
    afirmar_error_json(
        cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente), 409, "YA_UTILIZADA"
    )


@pytest.mark.parametrize("estado", ["pendiente", "vencida"])
def test_cancelar_compra_no_confirmada_devuelve_409(cliente_backend, cabeceras_cliente, bd, estado):
    bd.cursor.fetchone.return_value = _fila_cancelar(estado=estado)
    afirmar_error_json(
        cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente),
        409,
        "COMPRA_NO_CONFIRMADA",
    )


def test_cancelar_compra_fuera_de_plazo_devuelve_409(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_cancelar(fecha_hora=datetime.now() + timedelta(minutes=45))
    afirmar_error_json(
        cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente), 409, "FUERA_DE_PLAZO"
    )


def test_cancelar_compra_ok_invalida_qr_y_libera_butacas(cliente_backend, cabeceras_cliente, bd):
    respuesta = cliente_backend.post(f"/api/compras/{COMPRA_ID}/cancelar", headers=cabeceras_cliente)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": COMPRA_ID, "estado": "cancelada"}
    sentencias = [llamada.args[0] for llamada in bd.cursor.execute.call_args_list]
    assert "FOR UPDATE" in sentencias[0]
    assert any("SET estado = 'cancelada', cancelada_en = NOW(), token_qr = NULL" in sql for sql in sentencias)
    assert any("UPDATE entradas SET activa = NULL" in sql for sql in sentencias)


# --- POST /api/compras/cancelar-por-token (público) ---
def test_cancelar_por_token_valido_no_pide_sesion_y_cancela(cliente_backend, bd, token_cancelacion):
    respuesta = cliente_backend.post("/api/compras/cancelar-por-token", json={"token": token_cancelacion})
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": COMPRA_ID, "estado": "cancelada"}


@pytest.mark.parametrize("cuerpo", [{}, {"token": ""}, {"token": "falso"}, {"token": 123}])
def test_cancelar_por_token_invalido_devuelve_400(cliente_backend, bd, cuerpo):
    respuesta = cliente_backend.post("/api/compras/cancelar-por-token", json=cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] in ("DATOS_INVALIDOS", "TOKEN_INVALIDO")
    bd.cursor.execute.assert_not_called()
