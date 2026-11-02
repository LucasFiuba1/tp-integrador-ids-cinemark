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


def _formato_argentino(valor, decimales):
    """Separador de miles con punto y decimales con coma. Si no es un número devuelve None."""
    try:
        cantidad = float(valor)
    except (TypeError, ValueError):
        return None
    decimales = 0 if cantidad.is_integer() else decimales
    return f"{cantidad:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def numero(valor):
    """1742 -> 1.742 y 4.2 -> 4,2 (un decimal, formato argentino). Si no es un número lo devuelve tal cual."""
    texto = _formato_argentino(valor, 1)
    return valor if texto is None else texto


def precio(valor):
    """6500 -> $6.500 y 6500.5 -> $6.500,50 (formato argentino). Si no es un número lo devuelve tal cual."""
    texto = _formato_argentino(valor, 2)
    return valor if texto is None else f"${texto}"


def registrar_filtros(app):
    app.jinja_env.filters.update(fecha_hora=fecha_hora, hora=hora, numero=numero, precio=precio)
