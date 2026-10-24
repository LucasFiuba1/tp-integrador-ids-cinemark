"""Estadísticas del backoffice (SCRUM-29).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint

dashboards_bp = Blueprint("dashboards", __name__, url_prefix="/api/admin/dashboards")
