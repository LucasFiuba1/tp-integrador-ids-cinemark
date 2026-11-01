"""Registro, login y datos del usuario actual (SCRUM-17, SCRUM-18)."""
from flask import Blueprint, g, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.errores import error_api
from src.backend.services import usuarios

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _cuerpo_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        error_api(400, "DATOS_INVALIDOS", "El cuerpo debe ser un objeto JSON.")
    return datos


@auth_bp.post("/registro")
def registrar():
    return jsonify(usuarios.registrar(_cuerpo_json())), 201


@auth_bp.post("/login")
def iniciar_sesion():
    return jsonify(usuarios.iniciar_sesion(_cuerpo_json()))


@auth_bp.get("/me")
@requiere_rol("cliente", "admin")
def obtener_actual():
    return jsonify(usuarios.obtener_actual(g.usuario))
