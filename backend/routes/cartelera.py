"""Cartelera pública, detalle de películas, funciones y butacas (SCRUM-20, SCRUM-21).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint

cartelera_bp = Blueprint("cartelera", __name__, url_prefix="/api")
