"""Tokens firmados del QR de ingreso y del enlace de cancelación del email (SCRUM-4, SCRUM-67).

Ambos llevan {"compra_id": N} firmado con SECRET_KEY (igual que auth.py), pero cada uso tiene su propio salt:
un token de QR no sirve para cancelar y uno de cancelación no sirve para entrar a la sala.
No vencen por sí mismos: la validez la deciden las reglas de negocio (fecha de la función y plazo de cancelación).
"""
from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer

SALT_QR = "qr"
SALT_CANCELACION = "cancelar"


def _serializador(salt):
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=salt)


def _firmar(salt, compra_id):
    return _serializador(salt).dumps({"compra_id": compra_id})


def _leer(salt, token):
    """Devuelve el compra_id del token, o None si está vacío, fue alterado o es de otro uso."""
    if type(token) is not str or not token:
        return None
    try:
        datos = _serializador(salt).loads(token)
    except BadSignature:
        return None
    compra_id = datos.get("compra_id") if type(datos) is dict else None
    return compra_id if type(compra_id) is int else None


def firmar_qr(compra_id):
    return _firmar(SALT_QR, compra_id)


def leer_qr(token):
    return _leer(SALT_QR, token)


def firmar_cancelacion(compra_id):
    return _firmar(SALT_CANCELACION, compra_id)


def leer_cancelacion(token):
    return _leer(SALT_CANCELACION, token)
