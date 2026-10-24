"""Reserva de butacas, servicios, checkout, cancelación y perfil (SCRUM-1, 2, 3, 25, 26).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint

compras_bp = Blueprint("compras", __name__, url_prefix="/api")
