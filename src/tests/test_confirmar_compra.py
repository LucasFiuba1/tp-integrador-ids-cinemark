"""Pruebas de POST /api/compras/<id>/confirmar (SCRUM-66, SCRUM-67)."""
import base64
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.backend.tokens import leer_qr
from src.tests.utilidades import ID_CLIENTE, afirmar_error_json, simular_bd

RUTA = "/api/compras/88/confirmar"


def _fila_compra(**cambios):
    fila = {
        "id": 88,
        "usuario_id": ID_CLIENTE,
        "estado": "pendiente",
        "total": Decimal("23000.00"),
        "vencida": 0,
    }
    fila.update(cambios)
    return fila


def _detalle_compra():
    return {
        "id": 88,
        "estado": "confirmada",
        "total": 23000.0,
        "funcion": {
            "id": 12,
            "fecha_hora": "2026-11-10T20:30:00",
            "pelicula_id": 3,
            "pelicula": "Volver al futuro",
            "poster_url": None,
            "sala": "Sala 1",
            "local": "Paradiso Centro",
        },
        "butacas": ["D5", "D6"],
        "servicios": [],
        "cancelable": True,
        "cancelable_hasta": "2026-11-10T18:30:00",
    }


@pytest.fixture
def bd():
    with simular_bd(destinos=("src.backend.services.compras", "src.backend.services.perfil")) as simulacion:
        simulacion.cursor.fetchone.return_value = _fila_compra()
        yield simulacion


def test_confirmar_sin_token_devuelve_401(cliente_backend):
    afirmar_error_json(cliente_backend.post(RUTA), 401, "NO_AUTENTICADO")


def test_confirmar_con_rol_admin_devuelve_403(cliente_backend, cabeceras_admin):
    afirmar_error_json(cliente_backend.post(RUTA, headers=cabeceras_admin), 403, "SIN_PERMISO")


def test_confirmar_compra_inexistente_devuelve_404(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = None
    afirmar_error_json(cliente_backend.post(RUTA, headers=cabeceras_cliente), 404, "NO_ENCONTRADO")


def test_confirmar_compra_de_otro_usuario_devuelve_403(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_compra(usuario_id=999)
    afirmar_error_json(cliente_backend.post(RUTA, headers=cabeceras_cliente), 403, "SIN_PERMISO")


@pytest.mark.parametrize("estado", ["confirmada", "cancelada", "vencida"])
def test_confirmar_compra_no_pendiente_devuelve_409(cliente_backend, cabeceras_cliente, bd, estado):
    bd.cursor.fetchone.return_value = _fila_compra(estado=estado)
    afirmar_error_json(cliente_backend.post(RUTA, headers=cabeceras_cliente), 409, "COMPRA_NO_PENDIENTE")


def test_confirmar_reserva_vencida_libera_butacas_y_devuelve_409(cliente_backend, cabeceras_cliente, bd):
    bd.cursor.fetchone.return_value = _fila_compra(vencida=1)
    afirmar_error_json(cliente_backend.post(RUTA, headers=cabeceras_cliente), 409, "RESERVA_VENCIDA")
    sentencias = [llamada.args[0] for llamada in bd.cursor.execute.call_args_list]
    assert any("UPDATE compras SET estado = 'vencida'" in sql for sql in sentencias)
    assert any("UPDATE entradas SET activa = NULL" in sql for sql in sentencias)


def test_confirmar_compra_ok_genera_qr_firmado_y_envia_factura(cliente_backend, cabeceras_cliente, usuarios, bd):
    usuarios["cliente"]["email"] = "cliente@cine.com"
    with (
        patch("src.backend.services.compras.perfil.obtener_compra", return_value=_detalle_compra()),
        patch("src.backend.services.compras.correo.enviar_factura", return_value=True) as enviar_factura,
    ):
        respuesta = cliente_backend.post(RUTA, headers=cabeceras_cliente)

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["id"] == 88
    assert datos["estado"] == "confirmada"
    assert datos["total"] == 23000.0
    assert datos["email_enviado"] is True

    qr_bytes = base64.b64decode(datos["qr_png_base64"])
    assert qr_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    sql_update, parametros = bd.cursor.execute.call_args_list[1].args
    assert "SET estado = 'confirmada', confirmada_en = NOW(), token_qr = %s" in sql_update
    token_guardado, id_actualizado = parametros
    assert id_actualizado == 88
    assert leer_qr(token_guardado) == 88

    enviar_factura.assert_called_once_with(
        _detalle_compra(), {"nombre": "Cliente", "email": "cliente@cine.com"}, qr_bytes
    )


def test_confirmar_compra_cuando_falla_el_smtp_confirma_igual_con_email_enviado_false(
    cliente_backend, cabeceras_cliente, bd
):
    with (
        patch("src.backend.services.compras.perfil.obtener_compra", return_value=_detalle_compra()),
        patch("src.backend.services.compras.correo.enviar_factura", return_value=False),
    ):
        respuesta = cliente_backend.post(RUTA, headers=cabeceras_cliente)

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["estado"] == "confirmada"
    assert datos["email_enviado"] is False
