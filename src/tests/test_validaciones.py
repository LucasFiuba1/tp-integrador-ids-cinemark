"""Pruebas de validaciones compartidas del backend (SCRUM-98)."""
from datetime import datetime

import pytest
from werkzeug.exceptions import HTTPException

from src.backend.app import create_app
from src.backend.services.validaciones import (
    email_valido,
    entero_positivo,
    fecha_hora_iso,
    requerir_campos,
    texto_no_vacio,
)


def _verificar_error(funcion, *args):
    app = create_app()
    with app.test_request_context("/"), pytest.raises(HTTPException) as contexto:
        funcion(*args)
    respuesta = contexto.value.get_response()
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"


def test_requerir_campos_acepta_payload_completo():
    assert requerir_campos({"nombre": "Ana"}, ("nombre",)) is None


def test_requerir_campos_rechaza_objeto_o_clave_faltante():
    for datos in ([], {}):
        _verificar_error(requerir_campos, datos, ("nombre",))


def test_entero_positivo_valida_tipo_y_rango():
    assert entero_positivo(5, "id") == 5
    for valor in (0, -1, True, "2", 2.0):
        _verificar_error(entero_positivo, valor, "id")


def test_texto_no_vacio_valida_limite():
    assert texto_no_vacio(" Ana ", "nombre", 3) == "Ana"
    for valor in (" ", 5, "cuatro"):
        _verificar_error(texto_no_vacio, valor, "nombre", 3)


def test_email_valido_normaliza_a_minusculas():
    assert email_valido(" Ana@Mail.com ") == "ana@mail.com"
    for valor in ("", "ana@", "ana@mail", "a" * 150 + "@mail.com"):
        _verificar_error(email_valido, valor)


def test_fecha_hora_iso_parsea_formato_exacto():
    assert fecha_hora_iso("2026-11-01T14:30:00", "fecha") == datetime(2026, 11, 1, 14, 30)
    for valor in ("2026-1-1T4:00:00", "ayer", None):
        _verificar_error(fecha_hora_iso, valor, "fecha")
