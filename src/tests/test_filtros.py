"""Pruebas del helper común de filtros de listados (SCRUM-106) y de cómo lo usa cada listado."""
from datetime import datetime
from unittest.mock import patch

import pytest
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import HTTPException

from src.backend.filtros import VACIO_SE_IGNORA, construir_condiciones

FILTROS = {
    "local_id": ("s.local_id", "entero"),
    "fecha": ("f.fecha_hora", "dia"),
    "desde": ("f.fecha_hora", "desde"),
    "hasta": ("f.fecha_hora", "hasta"),
}


def _afirmar_400(funcion):
    with pytest.raises(HTTPException) as error:
        funcion()
    assert error.value.response.status_code == 400
    assert error.value.response.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"


# --- helper ---
def test_sin_filtros_no_agrega_condiciones():
    assert construir_condiciones({}, FILTROS) == ("", ())


def test_recibe_request_args_y_arma_una_condicion_por_tipo(app_backend):
    argumentos = MultiDict({"local_id": "3", "fecha": "2026-11-10", "desde": "2026-11-10T14:00:00",
                            "hasta": "2026-11-10T23:59:59"})
    clausulas, parametros = construir_condiciones(argumentos, FILTROS)
    assert clausulas == (" AND s.local_id = %s AND f.fecha_hora >= %s AND f.fecha_hora < %s"
                         " AND f.fecha_hora >= %s AND f.fecha_hora <= %s")
    assert parametros == (3, datetime(2026, 11, 10), datetime(2026, 11, 11), datetime(2026, 11, 10, 14),
                          datetime(2026, 11, 10, 23, 59, 59))


def test_los_valores_nunca_se_pegan_al_sql_y_los_parametros_desconocidos_se_ignoran(app_backend):
    argumentos = {"local_id": "7", "genero": "Drama", "s.local_id = 1 OR 1": "1", "orden": "titulo; DROP TABLE x"}
    clausulas, parametros = construir_condiciones(argumentos, FILTROS)
    assert clausulas == " AND s.local_id = %s"
    assert parametros == (7,)
    assert "7" not in clausulas and "Drama" not in clausulas and "DROP" not in clausulas


def test_el_orden_de_las_condiciones_es_el_del_mapa(app_backend):
    argumentos = {"hasta": "2026-11-10T23:59:59", "local_id": "2"}
    assert construir_condiciones(argumentos, FILTROS)[1] == (2, datetime(2026, 11, 10, 23, 59, 59))


@pytest.mark.parametrize("argumentos", [
    {"local_id": "abc"}, {"local_id": "0"}, {"local_id": "-1"}, {"local_id": "1.5"}, {"local_id": "²"},
    {"local_id": "1" * 19}, {"local_id": "9" * 5000},
    {"fecha": "ayer"}, {"fecha": "2026-13-01"}, {"fecha": "2026-11-10T10:00:00"},
    {"desde": "2026-11-10"}, {"hasta": "2026-11-10T24:00:00"},
    {"desde": "2026-11-10T10:00:01", "hasta": "2026-11-10T10:00:00"},
])
def test_valores_invalidos_cortan_con_400(app_backend, argumentos):
    _afirmar_400(lambda: construir_condiciones(argumentos, FILTROS))


def test_acepta_ids_de_hasta_18_digitos_y_desde_igual_a_hasta(app_backend):
    instante = "2026-11-10T20:00:00"
    _, parametros = construir_condiciones({"local_id": "9" * 18, "desde": instante, "hasta": instante}, FILTROS)
    assert parametros == (int("9" * 18), datetime(2026, 11, 10, 20), datetime(2026, 11, 10, 20))


@pytest.mark.parametrize("nombre", ["local_id", "fecha", "desde", "hasta"])
def test_vacio_da_400_por_defecto_y_se_ignora_si_el_listado_lo_pide(app_backend, nombre):
    _afirmar_400(lambda: construir_condiciones({nombre: ""}, FILTROS))
    assert construir_condiciones({nombre: ""}, FILTROS, vacio=VACIO_SE_IGNORA) == ("", ())


def test_un_valor_que_no_es_texto_da_400(app_backend):
    _afirmar_400(lambda: construir_condiciones({"local_id": 3}, FILTROS))


# --- cada listado conserva su contrato ---
@pytest.fixture
def consultas():
    """Simula la base de los cuatro listados y devuelve sus mocks de `consultar`."""
    with (patch("src.backend.services.cartelera.consultar", return_value=[]) as cartelera,
          patch("src.backend.services.funciones.consultar", return_value=[]) as funciones,
          patch("src.backend.services.salas.db.consultar", return_value=[]) as salas,
          patch("src.backend.services.ingresos.consultar", return_value=[]) as ingresos):
        yield {"cartelera": cartelera, "funciones": funciones, "salas": salas, "ingresos": ingresos}


@pytest.mark.parametrize("ruta", [
    "/api/cartelera?local_id=", "/api/cartelera?fecha=", "/api/admin/ingresos?funcion_id=",
    "/api/cartelera?local_id=" + "9" * 5000,  # antes int() rompía con un 500
])
def test_listados_que_rechazan_vacios_o_invalidos(cliente_backend, cabeceras_admin, consultas, ruta):
    respuesta = cliente_backend.get(ruta, headers=cabeceras_admin)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"


@pytest.mark.parametrize("ruta, listado", [
    ("/api/admin/funciones?local_id=&desde=&hasta=", "funciones"),
    ("/api/admin/salas?local_id=", "salas"),
])
def test_listados_del_backoffice_ignoran_filtros_vacios(cliente_backend, cabeceras_admin, consultas, ruta, listado):
    respuesta = cliente_backend.get(ruta, headers=cabeceras_admin)
    assert respuesta.status_code == 200
    sql, parametros = consultas[listado].call_args.args
    assert "local_id = %s" not in sql and parametros == ()


@pytest.mark.parametrize("valor", ["abc", "0", "-1"])
def test_salas_con_local_invalido_devuelve_400_en_vez_de_listar_todas(cliente_backend, cabeceras_admin, consultas,
                                                                       valor):
    respuesta = cliente_backend.get(f"/api/admin/salas?local_id={valor}", headers=cabeceras_admin)
    assert respuesta.status_code == 400
    consultas["salas"].assert_not_called()
