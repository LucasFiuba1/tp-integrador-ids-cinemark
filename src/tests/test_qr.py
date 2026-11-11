"""Pruebas del QR de ingreso: PNG y URL de validación codificada (SCRUM-4, SCRUM-67)."""
import struct
from urllib.parse import parse_qs, urlsplit

from src.backend.services.qr import generar_png, generar_qr, url_ingreso
from src.backend.tokens import firmar_qr, leer_qr

CABECERA_PNG = b"\x89PNG\r\n\x1a\n"


def _ancho_y_alto(png):
    # El primer bloque de un PNG es IHDR: ancho y alto en 4 bytes cada uno, después de la cabecera y del largo/tipo.
    return struct.unpack(">II", png[16:24])


def test_generar_png_devuelve_una_imagen_png_cuadrada():
    png = generar_png("eyJjb21wcmFfaWQiOjg4fQ.firma")
    assert png.startswith(CABECERA_PNG)
    ancho, alto = _ancho_y_alto(png)
    assert ancho == alto and ancho > 0


def test_generar_png_con_textos_distintos_da_imagenes_distintas():
    assert generar_png("token-uno") != generar_png("token-dos")


def test_url_ingreso_usa_frontend_url_del_entorno(app_backend):
    app_backend.config["FRONTEND_URL"] = "https://cine.ejemplo.com"
    assert url_ingreso("abc.def") == "https://cine.ejemplo.com/admin/ingreso?token=abc.def"


def test_url_ingreso_codifica_el_token_y_se_puede_leer_de_vuelta(app_backend):
    token = firmar_qr(88)
    partes = urlsplit(url_ingreso(token))
    assert partes.path == "/admin/ingreso"
    assert leer_qr(parse_qs(partes.query)["token"][0]) == 88
    assert "token=a%2Bb%26c%3D" in url_ingreso("a+b&c=")


def test_generar_qr_codifica_la_url_de_ingreso_y_no_solo_el_token(app_backend):
    token = firmar_qr(88)
    png = generar_qr(token)
    assert png.startswith(CABECERA_PNG)
    assert png == generar_png(url_ingreso(token))
    assert png != generar_png(token)
