"""Pruebas de la cartelera pública, el detalle de películas y el mapa de butacas (SCRUM-20, SCRUM-21) con la base simulada."""
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


@pytest.mark.parametrize("consulta", ["local_id=abc", "local_id=0", "local_id=²", "fecha=ayer", "fecha=2026-13-01"])
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


# --- mapa de butacas (SCRUM-60) ---
FUNCION = {"id": 12, "fecha_hora": datetime(2099, 11, 10, 20, 30), "sala": "Sala 1"}


def butaca(id, numero, estado):
    return {"id": id, "fila": "A", "numero": numero, "estado": estado}


def pedir_butacas(cliente_backend, consultar, funcion, butacas):
    consultar.return_value = butacas
    with patch("src.backend.services.cartelera.consultar_uno", return_value=funcion):
        return cliente_backend.get("/api/funciones/12/butacas")


def test_mapa_de_butacas_es_publico_y_cuenta_las_libres(cliente_backend, consultar):
    butacas = [butaca(1, 1, "libre"), butaca(2, 2, "ocupada"), butaca(3, 3, "libre")]
    respuesta = pedir_butacas(cliente_backend, consultar, dict(FUNCION), butacas)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "funcion_id": 12, "sala": "Sala 1", "capacidad": 3, "libres": 2, "vendible": True, "butacas": butacas,
    }


def test_butaca_vendida_aparece_ocupada_y_tras_cancelar_aparece_libre(cliente_backend, consultar):
    vendida = pedir_butacas(cliente_backend, consultar, dict(FUNCION), [butaca(1, 1, "ocupada")])
    assert vendida.get_json()["butacas"][0]["estado"] == "ocupada"
    sql = consultar.call_args.args[0]
    # Solo cuentan entradas vigentes de compras confirmadas o pendientes sin vencer: las canceladas quedan libres.
    assert "LEFT JOIN entradas" in sql and "entradas.activa = 1" in sql
    assert "compras.estado = 'confirmada'" in sql and "'cancelada'" not in sql
    assert consultar.call_args.args[1][1] == 12

    cancelada = pedir_butacas(cliente_backend, consultar, dict(FUNCION), [butaca(1, 1, "libre")])
    assert cancelada.get_json()["butacas"][0]["estado"] == "libre"
    assert cancelada.get_json()["libres"] == 1


def test_mapa_de_butacas_no_expone_datos_de_compradores(cliente_backend, consultar):
    pedir_butacas(cliente_backend, consultar, dict(FUNCION), [])
    sql = consultar.call_args.args[0]
    assert "usuario" not in sql
    assert sql.startswith("SELECT butacas.id, butacas.fila, butacas.numero, IF(compras.id IS NULL, 'libre', 'ocupada') AS estado FROM")


def test_funcion_ya_iniciada_no_es_vendible(cliente_backend, consultar):
    iniciada = dict(FUNCION, fecha_hora=datetime(2020, 1, 1, 20, 0))
    respuesta = pedir_butacas(cliente_backend, consultar, iniciada, [butaca(1, 1, "libre")])
    assert respuesta.status_code == 200
    assert respuesta.get_json()["vendible"] is False


def test_mapa_de_butacas_de_funcion_inexistente_devuelve_404(cliente_backend, consultar):
    respuesta = pedir_butacas(cliente_backend, consultar, None, [])
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "NO_ENCONTRADO"
    consultar.assert_not_called()
