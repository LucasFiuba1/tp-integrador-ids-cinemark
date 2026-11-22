"""QR de ingreso de una compra (SCRUM-4, SCRUM-67).

El QR codifica la URL pública de la entrada, <FRONTEND_URL>/entrada?token=<token_qr>: al escanearlo con la cámara
del celular cualquiera ve los datos básicos de la entrada, el comprador ve su compra completa y el admin, además,
puede validar el ingreso (ver compras.obtener_por_qr).
Usa qrcode con el generador de PNG en Python puro (pypng), así no hace falta instalar Pillow.
"""
from io import BytesIO
from urllib.parse import urlencode

import qrcode
from flask import current_app
from qrcode.image.pure import PyPNGImage


def url_entrada(token_qr):
    """URL pública de la entrada, con la base del frontend tomada de FRONTEND_URL y el token codificado."""
    return f"{current_app.config['FRONTEND_URL']}/entrada?{urlencode({'token': token_qr})}"


def generar_png(texto):
    """Devuelve los bytes del PNG con el QR que codifica `texto`."""
    imagen = qrcode.make(texto, image_factory=PyPNGImage, box_size=8, border=2)
    salida = BytesIO()
    imagen.save(salida)
    return salida.getvalue()


def generar_qr(token_qr):
    """PNG del QR de ingreso de una compra: codifica url_entrada(token_qr)."""
    return generar_png(url_entrada(token_qr))
