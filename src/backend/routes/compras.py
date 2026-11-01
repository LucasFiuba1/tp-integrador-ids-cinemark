"""Reserva de butacas, servicios, checkout, cancelación y perfil (SCRUM-1, 2, 3, 25, 26)."""
from flask import Blueprint, g, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.errores import error_api
from src.backend.services import compras

compras_bp = Blueprint("compras", __name__, url_prefix="/api")


@compras_bp.post("/compras")
@requiere_rol("cliente")
def reservar_butacas():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        error_api(400, "DATOS_INVALIDOS", "El cuerpo debe ser un objeto JSON.")
    return jsonify(compras.reservar(g.usuario["id"], datos)), 201
