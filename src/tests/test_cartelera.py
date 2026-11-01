"""Pruebas de la cartelera pública y el detalle de películas (SCRUM-20, SCRUM-21) con la base simulada."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

PELICULA = {
    "id": 3, "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "s", "poster_url": None,
    "duracion_min": 116, "clasificacion": "PG", "genero": "Ciencia ficción",
    "disponible_desde": datetime(2026, 11, 1), "disponible_hasta": datetime(2026, 12, 15), "activa": 1,
}


@pytest.fixture
def consultar():
    with patch("src.backend.services.cartelera.consultar") as consultar:
        yield consultar


def test_cartelera_es_publica_y_trae_la_proxima_funcion(cliente_backend, consultar):
    consultar.return_value = [{"id": 3, "titulo": "Volver al futuro", "proxima_funcion": datetime(2026, 11, 10, 20, 30)}]
    respuesta = cliente_backend.get("/api/cartelera")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [{"id": 3, "titulo": "Volver al futuro", "proxima_funcion": "2026-11-10T20:30:00"}]
    sql = consultar.call_args.args[0]
    assert "MIN(funciones.fecha_hora)" in sql
    assert "GROUP BY peliculas.id" in sql


def test_cartelera_filtra_por_local_y_por_dia_con_un_rango(cliente_backend, consultar):
    consultar.return_value = []
    cliente_backend.get("/api/cartelera?local_id=2&fecha=2026-11-10")
    sql, parametros = consultar.call_args.args
    assert "LIKE" not in sql
    assert parametros[1:] == [2, datetime(2026, 11, 10), datetime(2026, 11, 11)]


@pytest.mark.parametrize("consulta", ["local_id=abc", "local_id=0", "fecha=ayer", "fecha=2026-13-01"])
def test_cartelera_con_filtros_invalidos_devuelve_400(cliente_backend, consultar, consulta):
    respuesta = cliente_backend.get(f"/api/cartelera?{consulta}")
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    consultar.assert_not_called()


def test_detalle_trae_la_pelicula_y_sus_funciones(cliente_backend, consultar):
    consultar.return_value = [{"id": 12, "fecha_hora": datetime(2026, 11, 10, 20, 30), "precio": Decimal("5500.00"),
                               "nombre_sala": "Sala 1", "nombre_local": "Paradiso Centro"}]
    with patch("src.backend.services.cartelera.consultar_uno", return_value=dict(PELICULA)):
        respuesta = cliente_backend.get("/api/peliculas/3")
    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    assert datos["disponible_desde"] == "2026-11-01T00:00:00"
    assert datos["activa"] is True
    assert datos["funciones"] == [{"id": 12, "fecha_hora": "2026-11-10T20:30:00", "precio": 5500.0,
                                   "nombre_sala": "Sala 1", "nombre_local": "Paradiso Centro"}]


def test_detalle_de_pelicula_inexistente_devuelve_404(cliente_backend, consultar):
    with patch("src.backend.services.cartelera.consultar_uno", return_value=None):
        respuesta = cliente_backend.get("/api/peliculas/99")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "NO_ENCONTRADO"
    consultar.assert_not_called()
