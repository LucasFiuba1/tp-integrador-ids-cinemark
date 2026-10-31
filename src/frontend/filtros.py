"""Filtros de Jinja para mostrar los datos de la API.

La API manda fecha y hora en un solo campo ISO (YYYY-MM-DDTHH:MM:SS); acá se formatean para la pantalla.
Si el valor no es una fecha válida se muestra tal cual, para que la página no se rompa.
"""
from datetime import datetime


def _formatear(valor, formato):
    try:
        return datetime.fromisoformat(valor).strftime(formato)
    except (TypeError, ValueError):
        return valor


def fecha_hora(valor):
    """2026-10-24T19:30:00 -> 24/10 · 19:30"""
    return _formatear(valor, "%d/%m · %H:%M")


def hora(valor):
    """2026-10-24T19:30:00 -> 19:30"""
    return _formatear(valor, "%H:%M")


def registrar_filtros(app):
    app.jinja_env.filters.update(fecha_hora=fecha_hora, hora=hora)
