"""Registro, login y datos del usuario actual (SCRUM-17, SCRUM-18).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
