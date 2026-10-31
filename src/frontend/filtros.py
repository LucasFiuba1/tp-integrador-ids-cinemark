"""Filtros de Jinja para mostrar los datos de la API.

La API manda fecha y hora en un solo campo ISO (YYYY-MM-DDTHH:MM:SS) y los precios como número;
acá se formatean para la pantalla.
Si el valor no tiene el formato esperado se muestra tal cual, para que la página no se rompa.
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


def precio(valor):
    """6500 -> $6.500 y 6500.5 -> $6.500,50 (formato argentino). Si no es un número lo devuelve tal cual."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return valor
    decimales = 0 if numero.is_integer() else 2
    texto = f"{numero:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"${texto}"


def registrar_filtros(app):
    app.jinja_env.filters.update(fecha_hora=fecha_hora, hora=hora, precio=precio)
