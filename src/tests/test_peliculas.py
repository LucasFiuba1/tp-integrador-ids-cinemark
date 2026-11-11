"""Pruebas del ABM de películas (SCRUM-52) con la base y TMDB simulados."""
from datetime import datetime
from unittest.mock import patch

import pytest

from src.tests.utilidades import afirmar_error_json, simular_bd

PELICULA_TMDB = {
    "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "Marty viaja en el tiempo.",
    "poster_url": "https://image.tmdb.org/t/p/w500/x.jpg", "duracion_min": 116,
    "clasificacion": "PG", "genero": "Ciencia ficción",
}
PERIODO = {"disponible_desde": "2026-11-01T00:00:00", "disponible_hasta": "2026-12-15T23:59:59"}
RUTA = "/api/admin/peliculas"


def fila(**extra):
    base = {
        "id": 3, "tmdb_id": 105, "titulo": "Volver al futuro", "sinopsis": "s",
        "poster_url": None, "duracion_min": 116, "clasificacion": "PG", "genero": "Ciencia ficción",
        "disponible_desde": datetime(2026, 11, 1), "disponible_hasta": datetime(2026, 12, 15, 23, 59, 59),
        "activa": 1,
    }
    return {**base, **extra}


@pytest.fixture
def bd():
    """Base simulada tal como la usa el service de películas (consultar_uno, ejecutar y el resto de db)."""
    with simular_bd(destinos=("src.backend.services.peliculas",)) as simulacion:
        simulacion.ejecutar.return_value = 3
        yield simulacion


@pytest.fixture
def detalle():
    """TMDB simulado, independiente de la base."""
    with patch("src.backend.services.peliculas.tmdb.detalle", return_value=PELICULA_TMDB) as detalle:
        yield detalle


# --- protección ---
def test_sin_token_devuelve_401(cliente_backend):
    afirmar_error_json(cliente_backend.get(RUTA), 401, "NO_AUTENTICADO")


def test_cliente_devuelve_403(cliente_backend, cabeceras, usuario):
    usuario["rol"] = "cliente"
    afirmar_error_json(cliente_backend.get(RUTA, headers=cabeceras), 403, "SIN_PERMISO")


def test_token_invalido_devuelve_401(cliente_backend):
    respuesta = cliente_backend.get(RUTA, headers={"Authorization": "Bearer cualquiera"})
    afirmar_error_json(respuesta, 401, "TOKEN_INVALIDO")


# --- alta ---
def test_alta_importa_pelicula(cliente_backend, cabeceras, bd, detalle):
    bd.consultar_uno.side_effect = [None, fila()]  # no existe; luego se relee
    respuesta = cliente_backend.post(RUTA, json={"tmdb_id": 105, **PERIODO}, headers=cabeceras)
    assert respuesta.status_code == 201
    assert respuesta.get_json()["titulo"] == "Volver al futuro"
    assert respuesta.get_json()["disponible_desde"] == "2026-11-01T00:00:00"
    bd.ejecutar.assert_called_once()


def test_alta_con_muchos_generos_no_corta_uno_por_la_mitad(cliente_backend, cabeceras, bd, detalle):
    detalle.return_value = {**PELICULA_TMDB, "genero": "Animación, Aventura, Comedia, Familia, Fantasía, Ciencia ficción"}
    bd.consultar_uno.side_effect = [None, fila()]
    cliente_backend.post(RUTA, json={"tmdb_id": 105, **PERIODO}, headers=cabeceras)
    guardado = bd.ejecutar.call_args.args[1][6]
    assert guardado == "Animación, Aventura, Comedia, Familia, Fantasía"
    assert len(guardado) <= 50


def test_alta_duplicada_devuelve_409(cliente_backend, cabeceras, bd, detalle):
    bd.consultar_uno.return_value = {"id": 3}
    respuesta = cliente_backend.post(RUTA, json={"tmdb_id": 105, **PERIODO}, headers=cabeceras)
    afirmar_error_json(respuesta, 409, "PELICULA_DUPLICADA")
    detalle.assert_not_called()


@pytest.mark.parametrize("cuerpo", [
    {"disponible_desde": PERIODO["disponible_desde"]},
    {"tmdb_id": "abc", **PERIODO},
    {"tmdb_id": 105, "disponible_desde": "ayer", "disponible_hasta": PERIODO["disponible_hasta"]},
    {"tmdb_id": 105, "disponible_desde": PERIODO["disponible_hasta"], "disponible_hasta": PERIODO["disponible_desde"]},
])
def test_alta_con_datos_invalidos_devuelve_400(cliente_backend, cabeceras, cuerpo):
    respuesta = cliente_backend.post(RUTA, json=cuerpo, headers=cabeceras)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")


def test_alta_sin_cuerpo_json_devuelve_400(cliente_backend, cabeceras):
    afirmar_error_json(cliente_backend.post(RUTA, data="x", headers=cabeceras), 400, "DATOS_INVALIDOS")


# --- edición ---
def test_edicion_actualiza_periodo(cliente_backend, cabeceras, bd):
    bd.consultar_uno.side_effect = [fila(), fila(disponible_hasta=datetime(2027, 1, 31))]
    respuesta = cliente_backend.patch(f"{RUTA}/3", json={"disponible_hasta": "2027-01-31T00:00:00"}, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["disponible_hasta"] == "2027-01-31T00:00:00"
    assert "UPDATE peliculas" in bd.ejecutar.call_args.args[0]


@pytest.mark.parametrize("cuerpo", [
    {"disponible_hasta": "2026-10-01T00:00:00"},
    {"titulo": "  "},
    {"titulo": "x" * 201},
    {"genero": 5},
    {"duracion_min": 0},
    {"clasificacion": "x" * 11},
    {"poster_url": 3},
])
def test_edicion_con_datos_invalidos_devuelve_400(cliente_backend, cabeceras, bd, cuerpo):
    bd.consultar_uno.return_value = fila()
    afirmar_error_json(cliente_backend.patch(f"{RUTA}/3", json=cuerpo, headers=cabeceras), 400, "DATOS_INVALIDOS")
    bd.ejecutar.assert_not_called()


def test_edicion_acepta_clasificacion_y_poster_vacios(cliente_backend, cabeceras, bd):
    bd.consultar_uno.side_effect = [fila(), fila(clasificacion=None)]
    respuesta = cliente_backend.patch(f"{RUTA}/3", json={"clasificacion": None, "poster_url": None}, headers=cabeceras)
    assert respuesta.status_code == 200


def test_put_de_pelicula_devuelve_405(cliente_backend, cabeceras):
    respuesta = cliente_backend.put(f"{RUTA}/3", json={"titulo": "x"}, headers=cabeceras)
    afirmar_error_json(respuesta, 405, "METODO_NO_PERMITIDO")


def test_edicion_de_inexistente_devuelve_404(cliente_backend, cabeceras, bd):
    bd.consultar_uno.return_value = None
    respuesta = cliente_backend.patch(f"{RUTA}/99", json={"titulo": "x"}, headers=cabeceras)
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")


# --- baja ---
@pytest.mark.parametrize("tiene_funciones, baja, sql", [
    (1, "logica", "UPDATE peliculas SET activa = FALSE"),
    (0, "fisica", "DELETE FROM peliculas"),
])
def test_baja_logica_si_tiene_funciones_y_fisica_si_no(cliente_backend, cabeceras, bd, tiene_funciones, baja, sql):
    bd.consultar_uno.side_effect = [fila(), {"tiene_funciones": tiene_funciones}]
    respuesta = cliente_backend.delete(f"{RUTA}/3", headers=cabeceras)
    assert respuesta.get_json()["baja"] == baja
    assert sql in bd.ejecutar.call_args.args[0]


# --- búsqueda TMDB ---
def test_busqueda_tmdb(cliente_backend, cabeceras):
    with patch("src.backend.services.peliculas.tmdb.buscar", return_value=[{"tmdb_id": 105}]) as buscar:
        respuesta = cliente_backend.get("/api/admin/tmdb/buscar?q=futuro", headers=cabeceras)
    assert respuesta.get_json() == [{"tmdb_id": 105}]
    buscar.assert_called_once_with("futuro")


def test_busqueda_sin_q_devuelve_400(cliente_backend, cabeceras):
    afirmar_error_json(cliente_backend.get("/api/admin/tmdb/buscar", headers=cabeceras), 400, "DATOS_INVALIDOS")
