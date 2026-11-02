"""Pruebas de los templates maquetados de pago, compra confirmada (SCRUM-114) y cancelación (SCRUM-115)."""
import unittest
from datetime import date
from unittest.mock import patch

import pytest

from src.frontend.filtros import precio
from src.frontend.routes import publico
from src.frontend.validaciones import validar_pago

PAGO_VALIDO = {"titular": "Lucas Berardi", "numero": "4242 4242 4242 4242", "vencimiento": "12/28",
               "codigo_seguridad": "123", "acepto": "si"}
HOY = date(2026, 10, 31)


# --- pantallas ---
def test_pago_muestra_pasos_formulario_y_resumen(cliente_logueado):
    respuesta = cliente_logueado.get("/compras/1042/pago")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert '<li class="paso paso-hecho">' in html
    assert '<li class="paso paso-actual" aria-current="step">' in html
    assert '<form id="formulario-pago" method="post" action="/compras/1042/pago" novalidate>' in html
    for nombre in ("titular", "numero", "vencimiento", "codigo_seguridad", "acepto"):
        assert f'name="{nombre}"' in html
    assert 'form="formulario-pago">Confirmar y pagar</button>' in html
    for dato in ("La noche del telón", "3 entradas", "Combo pochoclos grande × 1", "$16.500", "$23.000", "19:05"):
        assert dato in html


def test_pago_valido_redirige_a_compra_confirmada(cliente_logueado):
    respuesta = cliente_logueado.post("/compras/1042/pago", data=PAGO_VALIDO)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/compras/1042/confirmada"


def test_pago_con_errores_devuelve_400_sin_repetir_los_datos_de_la_tarjeta(cliente_logueado):
    respuesta = cliente_logueado.post("/compras/1042/pago", data=dict(PAGO_VALIDO, vencimiento="13/28", acepto=""))
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert 'id="error-vencimiento">Ingresá el vencimiento como MM/AA' in html
    assert 'id="error-acepto">Tenés que aceptar' in html
    assert 'value="Lucas Berardi"' in html
    assert 'value="4242' not in html
    assert 'value="123"' not in html


def test_compra_confirmada_muestra_qr_y_datos(cliente_logueado):
    respuesta = cliente_logueado.get("/compras/1042/confirmada")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "¡Compra confirmada!" in html
    assert 'src="data:image/png;base64,iVBORw0KGgo' in html
    assert 'alt="Código QR de ingreso de la compra #1042"' in html
    for dato in ("Paradiso Centro", "24/10 · 19:30", "D5, D6, D7", "Combo pochoclos grande × 1"):
        assert f"<dd>{dato}</dd>" in html
    assert "<strong>$23.000</strong>" in html
    assert "lucas@email.com" in html
    assert 'href="/">Volver a cartelera</a>' in html


# --- validación del pago ---
def test_datos_validos_no_tienen_errores():
    assert validar_pago(PAGO_VALIDO, HOY) == {}
    assert validar_pago(dict(PAGO_VALIDO, vencimiento="10/26"), HOY) == {}


@pytest.mark.parametrize("campo, valor, mensaje", [
    ("titular", "", "Ingresá el nombre del titular"),
    ("titular", "x" * 101, "hasta 100 caracteres"),
    ("numero", "", "Ingresá el número"),
    ("numero", "4242 abcd", "entre 13 y 19 dígitos"),
    ("numero", "4242", "entre 13 y 19 dígitos"),
    ("vencimiento", "1228", "MM/AA"),
    ("vencimiento", "09/26", "La tarjeta está vencida."),
    ("codigo_seguridad", "12", "3 o 4 dígitos"),
    ("codigo_seguridad", "12a", "3 o 4 dígitos"),
    ("acepto", "", "Tenés que aceptar"),
])
def test_cada_campo_invalido_tiene_su_mensaje(campo, valor, mensaje):
    errores = validar_pago(dict(PAGO_VALIDO, **{campo: valor}), HOY)
    assert list(errores) == [campo]
    assert mensaje in errores[campo]


def test_precio_usa_formato_argentino():
    assert precio(23000) == "$23.000"
    assert precio(6500.5) == "$6.500,50"
    assert precio(None) is None
