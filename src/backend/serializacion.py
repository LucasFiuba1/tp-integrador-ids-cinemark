"""Serialización común de filas de MySQL a estructuras compatibles con JSON (SCRUM-99)."""
from datetime import date, datetime
from decimal import Decimal


CAMPOS_BOOLEANOS = {"activa", "activo"}


def serializar(fila):
    """Convierte una fila de MySQL a valores compatibles con JSON."""
    if fila is None:
        return None

    resultado = {}

    for campo, valor in fila.items():
        if isinstance(valor, datetime):
            resultado[campo] = valor.isoformat(timespec="seconds")
        elif isinstance(valor, date):
            resultado[campo] = valor.isoformat()
        elif isinstance(valor, Decimal):
            resultado[campo] = float(valor)
        elif campo in CAMPOS_BOOLEANOS and type(valor) is int:
            resultado[campo] = bool(valor)
        else:
            resultado[campo] = valor

    return resultado


def serializar_lista(filas):
    """Serializa una lista de filas de MySQL."""
    return [serializar(fila) for fila in filas]