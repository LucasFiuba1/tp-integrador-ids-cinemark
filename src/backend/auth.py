"""Autenticación por token firmado y decorador de roles.

El token es el que devuelve el login: un payload {"user_id": ...} firmado con SECRET_KEY.
"""
from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from src.backend.db import consultar_uno
from src.backend.errores import error_api

VIGENCIA_TOKEN_SEGUNDOS = 8 * 60 * 60


def _serializador():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generar_token(usuario_id):
    return _serializador().dumps({"user_id": usuario_id})


def requiere_rol(*roles):
    """Exige un token válido y que el usuario tenga alguno de los roles dados."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            encabezado = request.headers.get("Authorization", "")
            if not encabezado.startswith("Bearer "):
                error_api(401, "NO_AUTENTICADO", "Tenés que iniciar sesión.")
            try:
                datos = _serializador().loads(
                    encabezado[len("Bearer "):], max_age=VIGENCIA_TOKEN_SEGUNDOS
                )
            except BadSignature:
                error_api(401, "TOKEN_INVALIDO", "El token es inválido o venció.")
            usuario = consultar_uno(
                "SELECT id, nombre, rol FROM usuarios WHERE id = %s", (datos.get("user_id"),)
            )
            if usuario is None:
                error_api(401, "TOKEN_INVALIDO", "El token es inválido o venció.")
            if usuario["rol"] not in roles:
                error_api(403, "SIN_PERMISO", "No tenés permiso para esta acción.")
            g.usuario = usuario
            return vista(*args, **kwargs)

        return envoltura

    return decorador
