"""Páginas para el cliente: cartelera, compra y perfil."""
from flask import Blueprint, render_template

from frontend.api_client import ErrorBackend, llamar

publico_bp = Blueprint("publico", __name__)


@publico_bp.get("/")
def inicio():
    try:
        estado_api = llamar("GET", "/api/salud").get("estado")
    except ErrorBackend as error:
        estado_api = error.mensaje
    return render_template("inicio.html", estado_api=estado_api)
