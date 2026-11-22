"""Pruebas de los catálogos públicos usados por los filtros."""

from datetime import datetime
from unittest.mock import patch

import pytest


@pytest.fixture
def consultar():
    with patch("src.backend.services.catalogos.consultar") as consultar:
        yield consultar


def test_generos_devuelve_generos_en_uso(cliente_backend, consultar):
    consultar.return_value = [
        {"valor": "Drama, Suspenso"},
        {"valor": "Drama"},
        {"valor": "Animación, Familia"},
    ]

    respuesta = cliente_backend.get("/api/catalogos/generos")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == [
        "Animación",
        "Drama",
        "Familia",
        "Suspenso",
    ]

    sql, parametros = consultar.call_args.args

    assert "peliculas.activa = TRUE" in sql
    assert "funciones.activa = TRUE" in sql
    assert "salas.activa = TRUE" in sql
    assert "funciones.fecha_hora >= %s" in sql
    assert len(parametros) == 1
    assert isinstance(parametros[0], datetime)


def test_generos_elimina_repetidos_y_vacios(cliente_backend, consultar):
    consultar.return_value = [
        {"valor": "Drama, Drama"},
        {"valor": " Drama , , Suspenso "},
        {"valor": ""},
        {"valor": None},
    ]

    respuesta = cliente_backend.get("/api/catalogos/generos")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == ["Drama", "Suspenso"]


def test_generos_sin_datos_devuelve_lista_vacia(cliente_backend, consultar):
    consultar.return_value = []

    respuesta = cliente_backend.get("/api/catalogos/generos")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == []


def test_clasificaciones_devuelve_valores_en_uso(cliente_backend, consultar):
    consultar.return_value = [
        {"valor": "+13"},
        {"valor": "ATP"},
        {"valor": "+16"},
    ]

    respuesta = cliente_backend.get("/api/catalogos/clasificaciones")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == ["+13", "+16", "ATP"]

    sql, parametros = consultar.call_args.args

    assert "peliculas.activa = TRUE" in sql
    assert "funciones.activa = TRUE" in sql
    assert "salas.activa = TRUE" in sql
    assert "peliculas.clasificacion IS NOT NULL" in sql
    assert len(parametros) == 1
    assert isinstance(parametros[0], datetime)


def test_clasificaciones_elimina_vacios_y_repetidos(cliente_backend, consultar):
    consultar.return_value = [
        {"valor": "ATP"},
        {"valor": " ATP "},
        {"valor": ""},
        {"valor": None},
    ]

    respuesta = cliente_backend.get("/api/catalogos/clasificaciones")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == ["ATP"]


def test_clasificaciones_sin_datos_devuelve_lista_vacia(cliente_backend, consultar):
    consultar.return_value = []

    respuesta = cliente_backend.get("/api/catalogos/clasificaciones")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == []