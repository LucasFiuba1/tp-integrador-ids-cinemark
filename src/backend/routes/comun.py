"""Helpers compartidos por los blueprints."""
from flask import request

from src.backend.errores import error_api


def cuerpo_json():
    """Devuelve el cuerpo del request; corta con 400 si no es un objeto JSON."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        error_api(400, "DATOS_INVALIDOS", "El cuerpo debe ser un objeto JSON.")
    return datos
