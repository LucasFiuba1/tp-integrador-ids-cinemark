"""Registro, login, recuperación de contraseña y datos del usuario actual (SCRUM-17, SCRUM-18).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, g, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.routes.comun import cuerpo_json
from src.backend.services import cuentas

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/registro")
def registrar():
    return jsonify(cuentas.registrar(cuerpo_json())), 201


@auth_bp.post("/login")
def iniciar_sesion():
    return jsonify(cuentas.iniciar_sesion(cuerpo_json()))


# Recuperación de contraseña: públicos como el login (quien la olvidó no tiene token). La seguridad la da el
# token firmado que llega por email, que vence a la hora y sirve una sola vez.
@auth_bp.post("/recuperar")
def solicitar_recuperacion():
    return jsonify(cuentas.solicitar_recuperacion(cuerpo_json()))


@auth_bp.get("/restablecer")
def validar_recuperacion():
    return jsonify(cuentas.validar_recuperacion(request.args.get("token", "")))


@auth_bp.post("/restablecer")
def restablecer_password():
    return jsonify(cuentas.restablecer_password(cuerpo_json()))


@auth_bp.get("/me")
@requiere_rol("cliente", "admin")
def obtener_actual():
    return jsonify(g.usuario)
