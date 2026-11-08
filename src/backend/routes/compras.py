"""Reserva de butacas, servicios, checkout, cancelación y perfil (SCRUM-1, 2, 3, 25, 26)."""
from flask import Blueprint, g, jsonify

from src.backend.auth import requiere_rol
from src.backend.routes.comun import cuerpo_json
from src.backend.services import compras

compras_bp = Blueprint("compras", __name__, url_prefix="/api")


@compras_bp.post("/compras")
@requiere_rol("cliente")
def reservar_butacas():
    return jsonify(compras.reservar(g.usuario["id"], cuerpo_json())), 201


@compras_bp.post("/compras/<int:compra_id>/confirmar")
@requiere_rol("cliente")
def confirmar_compra(compra_id):
    return jsonify(compras.confirmar(g.usuario, compra_id))
