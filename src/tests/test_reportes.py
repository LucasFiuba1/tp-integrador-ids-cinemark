"""Pruebas del helper común de reportes agregados de los dashboards (SCRUM-109).

Las de `construir_filtros` (rango de fechas y local) están en test_dashboards.py junto con los endpoints que lo usan;
acá se cubren el porcentaje sin división por cero y el formato único de las series, con filas simuladas.
"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.backend.services.reportes import porcentaje, punto_serie, total_de

OCUPACION = "/api/admin/dashboards/ocupacion"
CANCELACIONES = "/api/admin/dashboards/cancelaciones"
VENTAS_GENERO = "/api/admin/dashboards/ventas-genero"
FRANJAS = "/api/admin/dashboards/franjas-horarias"
CLAVES_SERIE = {"etiqueta", "valor", "porcentaje"}


@pytest.fixture
def bd():
    with patch("src.backend.services.dashboards.consultar", return_value=[]) as consultar:
        yield consultar


# porcentaje
@pytest.mark.parametrize("parte, total, esperado", [
    (1, 2, 50.0),
    (2, 2, 100.0),
    (0, 140, 0.0),
    (1, 3, 33.33),
    (2, 3, 66.67),
    (1, 420, 0.24),
    (1, 800, 0.13),  # 0.125: la mitad se redondea hacia arriba, como ROUND de MySQL (round() de Python daría 0.12)
    (Decimal("7"), Decimal("140"), 5.0),  # SUM de MySQL llega como Decimal
])
def test_porcentaje_redondea_a_dos_decimales(parte, total, esperado):
    resultado = porcentaje(parte, total)
    assert resultado == esperado
    assert type(resultado) is float


@pytest.mark.parametrize("total", [0, Decimal("0"), None])
def test_porcentaje_con_total_cero_o_nulo_devuelve_cero_sin_dividir(total):
    assert porcentaje(5, total) == 0.0


def test_porcentaje_con_parte_nula_devuelve_cero():
    assert porcentaje(None, 10) == 0.0


# formato de series
def test_punto_serie_tiene_etiqueta_valor_y_porcentaje():
    assert punto_serie("Drama", 3, 4) == {"etiqueta": "Drama", "valor": 3, "porcentaje": 75.0}


def test_punto_serie_con_total_cero_no_rompe():
    assert punto_serie("Sala vacía", 0, 0) == {"etiqueta": "Sala vacía", "valor": 0, "porcentaje": 0.0}


def test_total_de_suma_la_clave_de_todas_las_filas():
    assert total_de([{"entradas": 3}, {"entradas": Decimal("2")}], "entradas") == 5
    assert total_de([], "entradas") == 0


# endpoints: todas las series traen el mismo formato
def _filas_de_ocupacion(sql, parametros=None):
    if "funcion_id" in sql.split("FROM")[0]:
        return [{"funcion_id": 1, "pelicula": "Alien", "local": "Centro", "sala": "Sala 1",
                 "fecha_hora": datetime(2026, 11, 7, 21, 0, 0), "vendidas": 0, "capacidad": 0}]
    return [{"pelicula_id": 1, "pelicula": "Alien", "vendidas": Decimal("0"), "capacidad": Decimal("0")}]


def test_ocupacion_con_capacidad_cero_devuelve_cero_y_no_rompe(cliente_backend, cabeceras, bd):
    bd.side_effect = _filas_de_ocupacion
    respuesta = cliente_backend.get(OCUPACION, headers=cabeceras)
    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    for fila in datos["por_pelicula"] + datos["por_funcion"]:
        assert fila["ocupacion"] == 0.0 and fila["porcentaje"] == 0.0


def test_ocupacion_no_divide_en_el_select_y_ordena_por_la_misma_cuenta(cliente_backend, cabeceras, bd):
    cliente_backend.get(OCUPACION, headers=cabeceras)
    for llamada in bd.call_args_list:
        select, orden = llamada.args[0].split("ORDER BY")
        assert "/" not in select.split("FROM")[0]
        assert orden.strip().startswith("ROUND(100 *")


def test_cancelaciones_no_divide_en_el_select(cliente_backend, cabeceras, bd):
    cliente_backend.get(CANCELACIONES, headers=cabeceras)
    for llamada in bd.call_args_list:
        assert "/" not in llamada.args[0].split("FROM")[0]


def test_ventas_genero_reparte_el_porcentaje_sobre_el_total(cliente_backend, cabeceras, bd):
    bd.return_value = [{"genero": "Drama", "entradas": 3, "monto": Decimal("16500.00")},
                       {"genero": "Comedia", "entradas": 1, "monto": Decimal("5500.00")}]
    datos = cliente_backend.get(VENTAS_GENERO, headers=cabeceras).get_json()
    assert [(fila["etiqueta"], fila["valor"], fila["porcentaje"]) for fila in datos] == [
        ("Drama", 3, 75.0), ("Comedia", 1, 25.0)]


@pytest.mark.parametrize("ruta, filas, listas", [
    (FRANJAS, [{"hora_desde": 20, "entradas": 4}], None),
    (VENTAS_GENERO, [{"genero": "Drama", "entradas": 3, "monto": Decimal("1")}], None),
    (CANCELACIONES, [{"pelicula_id": 1, "pelicula": "Alien", "periodo": datetime(2026, 11, 7).date(),
                      "compras": 2, "canceladas": Decimal("1")}], ("por_pelicula", "por_periodo")),
    (OCUPACION, None, ("por_pelicula", "por_funcion")),
])
def test_todas_las_series_tienen_etiqueta_valor_y_porcentaje(cliente_backend, cabeceras, bd, ruta, filas, listas):
    if filas is None:
        bd.side_effect = _filas_de_ocupacion
    else:
        bd.return_value = filas
    datos = cliente_backend.get(ruta, headers=cabeceras).get_json()
    series = [datos] if listas is None else [datos[lista] for lista in listas]
    for serie in series:
        assert serie
        for fila in serie:
            assert CLAVES_SERIE <= set(fila)
            assert type(fila["valor"]) is int and type(fila["porcentaje"]) is float
