"""Páginas del administrador (ABM, dashboards y validación de QR)."""
from flask import Blueprint

backoffice_bp = Blueprint("backoffice", __name__, url_prefix="/admin")
