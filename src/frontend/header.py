"""Ayudas del header público (SCRUM-95).

El header ofrece secciones que todavía no tienen pantalla (Servicios, Mis compras, Mi perfil). En lugar de poner
links rotos, el template pregunta con ruta_disponible(endpoint) si la ruta ya existe: si existe la enlaza con
url_for y si no la muestra deshabilitada. Así, cuando se agregue la vista, el header la enlaza solo.
No llama al backend: el header se arma únicamente con la sesión, el request y lo que le pase la vista.
"""
from flask import current_app


def ruta_disponible(endpoint):
    """True si el endpoint está registrado y tiene alguna URL sin parámetros obligatorios (url_for no falla)."""
    if endpoint not in current_app.view_functions:
        return False
    return any(not regla.arguments for regla in current_app.url_map.iter_rules(endpoint))


def registrar_header(app):
    app.add_template_global(ruta_disponible)
