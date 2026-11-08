"""Pruebas de los tokens firmados del QR y de la cancelación por email (SCRUM-67)."""
import pytest
from itsdangerous import URLSafeSerializer

from src.backend.tokens import firmar_cancelacion, firmar_qr, leer_cancelacion, leer_qr


def test_firmar_qr_y_leerlo_devuelve_el_id_de_la_compra(app_backend):
    assert leer_qr(firmar_qr(88)) == 88


def test_firmar_cancelacion_y_leerla_devuelve_el_id_de_la_compra(app_backend):
    assert leer_cancelacion(firmar_cancelacion(88)) == 88


def test_token_de_qr_no_sirve_para_cancelar_ni_al_reves(app_backend):
    assert leer_cancelacion(firmar_qr(88)) is None
    assert leer_qr(firmar_cancelacion(88)) is None


def test_token_firmado_con_otra_clave_devuelve_none(app_backend):
    ajeno = URLSafeSerializer("otra-clave", salt="qr").dumps({"compra_id": 88})
    assert leer_qr(ajeno) is None


def test_token_alterado_devuelve_none(app_backend):
    token = firmar_qr(88)
    alterado = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert leer_qr(alterado) is None


@pytest.mark.parametrize("token", ["", None, 88, "no-es-un-token", ["lista"]])
def test_token_invalido_devuelve_none(app_backend, token):
    assert leer_qr(token) is None
    assert leer_cancelacion(token) is None


@pytest.mark.parametrize("contenido", [{"compra_id": "88"}, {"otro": 1}, [88], 88])
def test_token_bien_firmado_con_contenido_inesperado_devuelve_none(app_backend, contenido):
    token = URLSafeSerializer("pruebas", salt="qr").dumps(contenido)
    assert leer_qr(token) is None


def test_token_de_qr_entra_en_la_columna_token_qr(app_backend):
    assert len(firmar_qr(2_147_483_647)) <= 255
