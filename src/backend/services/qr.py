"""Imagen PNG del QR de ingreso (SCRUM-4, SCRUM-67).

Usa qrcode con el generador de PNG en Python puro (pypng), así no hace falta instalar Pillow.
"""
from io import BytesIO

import qrcode
from qrcode.image.pure import PyPNGImage


def generar_png(texto):
    """Devuelve los bytes del PNG con el QR que codifica `texto` (el token_qr de la compra)."""
    imagen = qrcode.make(texto, image_factory=PyPNGImage, box_size=8, border=2)
    salida = BytesIO()
    imagen.save(salida)
    return salida.getvalue()
