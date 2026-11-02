"""Perfil del cliente: compras y películas vistas (SCRUM-49).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, g, jsonify

from src.backend.auth import requiere_rol
from src.backend.services import perfil

perfil_bp = Blueprint("perfil", __name__, url_prefix="/api/me")


@perfil_bp.get("/compras")
@requiere_rol("cliente", "admin")
def listar_compras():
    return jsonify(perfil.listar_compras(g.usuario["id"]))


@perfil_bp.get("/peliculas-vistas")
@requiere_rol("cliente", "admin")
def listar_peliculas_vistas():
    return jsonify(perfil.listar_peliculas_vistas(g.usuario["id"]))
