"""Reserva de butacas, servicios, checkout, cancelación y perfil (SCRUM-1, 2, 3, 25, 26)."""
from flask import Blueprint, g, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.routes.comun import cuerpo_json
from src.backend.services import compras

compras_bp = Blueprint("compras", __name__, url_prefix="/api")


@compras_bp.post("/compras")
@requiere_rol("cliente")
def reservar_butacas():
    return jsonify(compras.reservar(g.usuario["id"], cuerpo_json())), 201


@compras_bp.get("/compras/<int:compra_id>")
@requiere_rol("cliente", "admin")
def obtener_compra(compra_id):
    return jsonify(compras.obtener(g.usuario, compra_id))


@compras_bp.get("/compras/por-token")
def obtener_compra_por_token():
    return jsonify(compras.obtener_por_token(request.args.get("token")))


@compras_bp.post("/compras/<int:compra_id>/cancelar")
@requiere_rol("cliente")
def cancelar_compra(compra_id):
    return jsonify(compras.cancelar(g.usuario["id"], compra_id))


@compras_bp.post("/compras/cancelar-por-token")
def cancelar_compra_por_token():
    return jsonify(compras.cancelar_por_token(cuerpo_json()))


@compras_bp.post("/compras/<int:compra_id>/confirmar")
@requiere_rol("cliente")
def confirmar_compra(compra_id):
    return jsonify(compras.confirmar(g.usuario, compra_id))
