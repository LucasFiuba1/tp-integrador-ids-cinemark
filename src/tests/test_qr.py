"""Pruebas de la imagen PNG del QR de ingreso (SCRUM-67)."""
import struct

from src.backend.services.qr import generar_png

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
