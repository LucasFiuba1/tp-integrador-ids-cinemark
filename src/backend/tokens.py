"""Tokens firmados del QR de ingreso y del enlace de cancelación del email (SCRUM-4, SCRUM-67).

Ambos llevan {"compra_id": N} firmado con SECRET_KEY (igual que auth.py), pero cada uso tiene su propio salt:
un token de QR no sirve para cancelar y uno de cancelación no sirve para entrar a la sala.
No vencen por sí mismos: la validez la deciden las reglas de negocio (fecha de la función y plazo de cancelación).

El token de recuperación de contraseña (olvidé mi contraseña) es distinto: lleva {"usuario_id": N, "huella": ...},
vence a la hora y la huella sale del password_hash actual. Al cambiar la contraseña la huella deja de coincidir,
así que el enlace sirve una sola vez sin guardar nada en la base.
"""
import hashlib

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer, URLSafeTimedSerializer

SALT_QR = "qr"
SALT_CANCELACION = "cancelar"
SALT_RECUPERACION = "recuperar-password"
VIGENCIA_RECUPERACION_SEGUNDOS = 60 * 60


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


def huella_password(password_hash):
    """Resumen corto del hash actual: el token no expone el hash, pero deja de valer cuando la contraseña cambia."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def _serializador_recuperacion():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT_RECUPERACION)


def firmar_recuperacion(usuario_id, password_hash):
    return _serializador_recuperacion().dumps({"usuario_id": usuario_id, "huella": huella_password(password_hash)})


def leer_recuperacion(token):
    """Devuelve (usuario_id, huella) del token, o None si está vacío, alterado, es de otro uso o venció."""
    if type(token) is not str or not token:
        return None
    try:
        datos = _serializador_recuperacion().loads(token, max_age=VIGENCIA_RECUPERACION_SEGUNDOS)
    except BadSignature:  # SignatureExpired es subclase de BadSignature
        return None
    if type(datos) is not dict or type(datos.get("usuario_id")) is not int or type(datos.get("huella")) is not str:
        return None
    return datos["usuario_id"], datos["huella"]
