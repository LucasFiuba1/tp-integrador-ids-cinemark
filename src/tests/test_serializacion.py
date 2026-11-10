"""Pruebas del helper común de serialización JSON (SCRUM-99)."""
from datetime import date, datetime
from decimal import Decimal

from src.backend.serializacion import serializar, serializar_lista


def test_serializar_convierte_tipos_de_mysql():
    fila = {
        "id": 3,
        "titulo": "Volver al futuro",
        "fecha_hora": datetime(2026, 11, 10, 20, 30),
        "fecha": date(2026, 11, 10),
        "precio": Decimal("8500.50"),
        "activa": 1,
        "descripcion": None,
    }

    resultado = serializar(fila)

    assert resultado["id"] == 3
    assert resultado["titulo"] == "Volver al futuro"
    assert resultado["fecha_hora"] == "2026-11-10T20:30:00"
    assert resultado["fecha"] == "2026-11-10"
    assert resultado["precio"] == 8500.50
    assert resultado["activa"] is True
    assert resultado["descripcion"] is None


def test_serializar_convierte_booleano_falso():
    resultado = serializar({"activa": 0})

    assert resultado["activa"] is False


def test_serializar_no_modifica_la_fila_original():
    fecha = datetime(2026, 11, 10, 20, 30)
    fila = {"fecha_hora": fecha}

    serializar(fila)

    assert fila["fecha_hora"] == fecha


def test_serializar_none_devuelve_none():
    assert serializar(None) is None


def test_serializar_lista_convierte_todas_las_filas():
    filas = [
        {"id": 1, "precio": Decimal("1000.00")},
        {"id": 2, "precio": Decimal("2500.50")},
    ]

    resultado = serializar_lista(filas)

    assert resultado == [
        {"id": 1, "precio": 1000.0},
        {"id": 2, "precio": 2500.5},
    ]