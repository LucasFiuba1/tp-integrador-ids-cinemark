"""Pruebas de dashboards: vista del backoffice (SCRUM-121 y 77) y franjas horarias / cancelaciones del
backend (SCRUM-76). Las del backend simulan la base (`consultar` de services/dashboards.py); la verificación
contra MySQL real está en test_dashboards_mysql.py (opt-in)."""
import re
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from werkzeug.exceptions import HTTPException

from src.backend.services.filtros_dashboards import construir_filtros
from src.frontend.filtros import numero

# Respuestas de ejemplo de GET /api/admin/dashboards/<tablero> (ver docs/endpoints.md).
RESPUESTAS = {
    "/api/admin/dashboards/franjas-horarias": [
        {"hora_desde": 18, "hora_hasta": 20, "entradas": 742}, {"hora_desde": 20, "hora_hasta": 22, "entradas": 510},
        {"hora_desde": 16, "hora_hasta": 18, "entradas": 310}, {"hora_desde": 14, "hora_hasta": 16, "entradas": 180},
    ],
    "/api/admin/dashboards/ocupacion": {
        "por_pelicula": [
            {"pelicula": "La noche del telón", "vendidas": 412, "capacidad": 560, "ocupacion": 73.6},
            {"pelicula": "Código Medianoche", "vendidas": 330, "capacidad": 500, "ocupacion": 66},
        ],
        "por_funcion": [],
    },
    "/api/admin/dashboards/ventas-genero": [
        {"genero": "Drama", "entradas": 1000, "monto": 2750000.00},
        {"genero": "Animación", "entradas": 742, "monto": 2070000.00},
    ],
    "/api/admin/dashboards/cancelaciones": {
        "por_pelicula": [
            {"pelicula_id": 2, "pelicula": "Código Medianoche", "compras": 300, "canceladas": 18, "porcentaje": 6.0},
            {"pelicula_id": 1, "pelicula": "La noche del telón", "compras": 200, "canceladas": 3, "porcentaje": 1.5},
        ],
        "por_periodo": [],
    },
    "/api/admin/locales": [{"id": 1, "nombre": "Paradiso Centro", "direccion": "Av. Corrientes 1234"}],
}


@pytest.fixture
def api(request):
    """Simula llamar(...) de la ruta con RESPUESTAS (o las que pase la prueba con indirect)."""
    respuestas = getattr(request, "param", RESPUESTAS)
    with patch("src.frontend.routes.backoffice.llamar",
               side_effect=lambda metodo, ruta, params=None: (respuestas.get(ruta), None)) as llamar:
        yield llamar


def test_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/dashboards")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_muestra_los_kpi_y_los_cuatro_tableros(cliente_admin, api):
    respuesta = cliente_admin.get("/admin/dashboards")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/dashboards" aria-current="page"' in html
    # 742 / 1060 butacas y 21 / 500 compras, sumando las respuestas de la API.
    for valor in ("1.742", "$4.820.000", "70%", "4,2%"):
        assert f'<p class="kpi-valor">{valor}</p>' in html
    for titulo in ("Entradas por franja horaria", "Ocupación por película", "Ventas por género",
                   "Cancelaciones por película", "Ocupación por función"):
        assert f">{titulo}</h2>" in html


def test_la_franja_mas_vendida_se_destaca_y_las_columnas_son_proporcionales(cliente_admin, api):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert html.count("columna-destacada") == 1
    assert 'style="height: calc(100.0% - var(--espacio-5))"' in html
    assert 'style="height: calc(24.3% - var(--espacio-5))"' in html  # 180 de 742
    assert '<span class="columna-etiqueta">18 a 20 h</span>' in html


def test_las_franjas_se_muestran_en_orden_horario(cliente_admin, api):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert re.findall(r'columna-etiqueta">(\d+) a', html) == ["14", "16", "18", "20"]


def test_la_tabla_muestra_solo_las_funciones_con_mayor_ocupacion(cliente_admin):
    funciones = [{"funcion_id": numero_funcion, "pelicula": f"Película {numero_funcion}", "local": "Centro", "sala": "Sala 1",
                  "fecha_hora": "2026-11-07T21:00:00", "vendidas": 1, "capacidad": 96, "ocupacion": 1.04}
                 for numero_funcion in range(1, 13)]
    respuestas = dict(RESPUESTAS)
    respuestas["/api/admin/dashboards/ocupacion"] = {"por_pelicula": [], "por_funcion": funciones}
    with patch("src.frontend.routes.backoffice.llamar",
               side_effect=lambda metodo, ruta, params=None: (respuestas.get(ruta), None)):
        html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert "Película 10" in html and "Película 11" not in html


@pytest.mark.parametrize("api", [{}], indirect=True)
def test_tableros_vacios_no_rompen_la_pagina(cliente_admin, api):
    respuesta = cliente_admin.get("/admin/dashboards")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert html.count("Todavía no hay datos para este período.") == 5
    assert 'class="columnas"' not in html


@pytest.mark.parametrize("api", [{
    "/api/admin/dashboards/ventas-genero": [
        {"genero": "Drama", "entradas": 4, "monto": 22000.0}, {"genero": "Terror", "entradas": 4, "monto": 22000.0},
        {"genero": "Comedia", "entradas": 1, "monto": 5500.0},
    ],
}], indirect=True)
def test_se_resaltan_todas_las_barras_empatadas_en_el_maximo(cliente_admin, api):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert html.count("barra-destacada") == 2


@pytest.mark.parametrize("api", [{
    "/api/admin/dashboards/cancelaciones": {
        "por_pelicula": [{"pelicula_id": 1, "pelicula": "Alien", "compras": 2, "canceladas": 0, "porcentaje": 0.0}],
        "por_periodo": [],
    },
}], indirect=True)
def test_sin_cancelaciones_no_se_resalta_ninguna_barra(cliente_admin, api):
    respuesta = cliente_admin.get("/admin/dashboards")
    assert respuesta.status_code == 200
    assert "barra-destacada" not in respuesta.get_data(as_text=True)


def test_numero_usa_formato_argentino():
    assert numero(1742) == "1.742"
    assert numero(4.2) == "4,2"
    assert numero(74) == "74"
    assert numero("sin dato") == "sin dato"


# --- backend: franjas horarias y cancelaciones (SCRUM-76) ---
FRANJAS = "/api/admin/dashboards/franjas-horarias"
CANCELACIONES = "/api/admin/dashboards/cancelaciones"
OCUPACION = "/api/admin/dashboards/ocupacion"
VENTAS_GENERO = "/api/admin/dashboards/ventas-genero"
RUTAS = (FRANJAS, CANCELACIONES, OCUPACION, VENTAS_GENERO)
DESDE = "2026-11-06T17:30:00"
HASTA = "2026-11-08T23:59:59"

# Filas tal como las devuelve MySQL: SUM/porcentaje llegan como Decimal y DATE() como date.
FILAS_FRANJAS = [
    {"hora_desde": 20, "hora_hasta": 22, "entradas": 4},
    {"hora_desde": 16, "hora_hasta": 18, "entradas": 1},
]
FILAS_PELICULAS = [
    {"pelicula_id": 7, "pelicula": "Jurassic Park", "compras": 2, "canceladas": Decimal("1"),
     "porcentaje": Decimal("50.00")},
    {"pelicula_id": 5, "pelicula": "El viaje de Chihiro", "compras": 1, "canceladas": Decimal("0"),
     "porcentaje": Decimal("0.00")},
]
FILAS_PERIODOS = [
    {"periodo": date(2026, 11, 6), "compras": 2, "canceladas": Decimal("0"), "porcentaje": Decimal("0.00")},
    {"periodo": date(2026, 11, 8), "compras": 2, "canceladas": Decimal("1"), "porcentaje": Decimal("50.00")},
]
PELICULAS_JSON = [
    {"pelicula_id": 7, "pelicula": "Jurassic Park", "compras": 2, "canceladas": 1, "porcentaje": 50.0},
    {"pelicula_id": 5, "pelicula": "El viaje de Chihiro", "compras": 1, "canceladas": 0, "porcentaje": 0.0},
]
PERIODOS_JSON = [
    {"periodo": "2026-11-06T00:00:00", "compras": 2, "canceladas": 0, "porcentaje": 0.0},
    {"periodo": "2026-11-08T00:00:00", "compras": 2, "canceladas": 1, "porcentaje": 50.0},
]


def _filas_segun_sql(filas_peliculas, filas_periodos):
    """Devuelve un side_effect de `consultar` que elige las filas según el SELECT (el de período tiene `periodo`)."""
    def consultar_falso(sql, parametros=None):
        return filas_periodos if "periodo" in sql.lower() else filas_peliculas
    return consultar_falso


@pytest.fixture
def bd():
    """Simula la base de dashboards: sin filas hasta que cada prueba configure `bd.side_effect`."""
    with patch("src.backend.services.dashboards.consultar", return_value=[]) as consultar:
        yield consultar


def _consultas(bd):
    """SQL (con espacios normalizados) y parámetros (lista) de cada llamada a `consultar`."""
    consultas = []
    for llamada in bd.call_args_list:
        sql = llamada.args[0] if llamada.args else llamada.kwargs["sql"]
        parametros = llamada.args[1] if len(llamada.args) > 1 else llamada.kwargs.get("parametros")
        consultas.append((" ".join(sql.split()), list(parametros or ())))
    return consultas


def _sql_y_valores(sql, parametros):
    """Los estados pueden ir como literal o como parámetro: se busca en ambos."""
    return sql.lower() + " " + " ".join(str(valor) for valor in parametros).lower()


def _orden(sql):
    return sql.upper().split("ORDER BY")[-1]


# 200 y respuestas vacías
def test_franjas_horarias_devuelve_200_con_las_franjas(cliente_backend, cabeceras, bd):
    bd.return_value = FILAS_FRANJAS
    respuesta = cliente_backend.get(FRANJAS, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [
        {"hora_desde": 20, "hora_hasta": 22, "entradas": 4},
        {"hora_desde": 16, "hora_hasta": 18, "entradas": 1},
    ]
    assert bd.call_count == 1


def test_franjas_horarias_sin_ventas_devuelve_lista_vacia(cliente_backend, cabeceras, bd):
    respuesta = cliente_backend.get(FRANJAS, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == []


def test_cancelaciones_devuelve_200_con_los_numeros_como_numeros(cliente_backend, cabeceras, bd):
    bd.side_effect = _filas_segun_sql(FILAS_PELICULAS, FILAS_PERIODOS)
    respuesta = cliente_backend.get(CANCELACIONES, headers=cabeceras)
    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    assert datos == {"por_pelicula": PELICULAS_JSON, "por_periodo": PERIODOS_JSON}
    for fila in datos["por_pelicula"] + datos["por_periodo"]:
        for campo in ("compras", "canceladas"):
            assert isinstance(fila[campo], int)
        assert isinstance(fila["porcentaje"], (int, float))


def test_cancelaciones_sin_compras_devuelve_las_dos_listas_vacias(cliente_backend, cabeceras, bd):
    respuesta = cliente_backend.get(CANCELACIONES, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"por_pelicula": [], "por_periodo": []}


def test_local_inexistente_devuelve_resultados_vacios_y_no_404(cliente_backend, cabeceras, bd):
    for ruta, vacio in ((FRANJAS, []), (CANCELACIONES, {"por_pelicula": [], "por_periodo": []})):
        respuesta = cliente_backend.get(ruta, query_string={"local_id": "9999"}, headers=cabeceras)
        assert respuesta.status_code == 200
        assert respuesta.get_json() == vacio


# seguridad
@pytest.mark.parametrize("ruta", RUTAS)
def test_dashboards_sin_token_devuelve_401_sin_consultar(cliente_backend, bd, ruta):
    respuesta = cliente_backend.get(ruta)
    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "NO_AUTENTICADO"
    bd.assert_not_called()


@pytest.mark.parametrize("ruta", RUTAS)
def test_dashboards_con_rol_cliente_devuelve_403_sin_consultar(cliente_backend, cabeceras, usuario, bd, ruta):
    usuario["rol"] = "cliente"
    respuesta = cliente_backend.get(ruta, headers=cabeceras)
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "SIN_PERMISO"
    bd.assert_not_called()


# filtros: parámetros del SELECT
def test_franjas_horarias_sin_filtros_no_agrega_condiciones_ni_parametros(cliente_backend, cabeceras, bd):
    cliente_backend.get(FRANJAS, headers=cabeceras)
    (sql, parametros), = _consultas(bd)
    assert parametros == []
    assert "%s" not in sql


def test_franjas_horarias_aplica_desde_hasta_y_local_con_tipos_exactos(cliente_backend, cabeceras, bd):
    respuesta = cliente_backend.get(FRANJAS, query_string={"desde": DESDE, "hasta": HASTA, "local_id": "3"},
                                    headers=cabeceras)
    (sql, parametros), = _consultas(bd)
    assert respuesta.status_code == 200
    assert len(parametros) == sql.count("%s") == 3
    assert parametros[0] == datetime(2026, 11, 6, 17, 30, 0) and type(parametros[0]) is datetime
    assert parametros[1] == datetime(2026, 11, 8, 23, 59, 59) and type(parametros[1]) is datetime
    assert parametros[2] == 3 and type(parametros[2]) is int
    assert "2026" not in sql  # los datos del usuario van como parámetros, nunca dentro del SQL


@pytest.mark.parametrize("ruta", RUTAS)
def test_los_extremos_de_fecha_son_inclusivos(cliente_backend, cabeceras, bd, ruta):
    cliente_backend.get(ruta, query_string={"desde": DESDE, "hasta": HASTA}, headers=cabeceras)
    consultas = _consultas(bd)
    assert consultas
    for sql, parametros in consultas:
        assert re.search(r"fecha_hora\s*>=\s*%s", sql) and re.search(r"fecha_hora\s*<=\s*%s", sql)
        assert parametros == [datetime(2026, 11, 6, 17, 30, 0), datetime(2026, 11, 8, 23, 59, 59)]


@pytest.mark.parametrize("filtros, esperado", [
    ({"desde": DESDE}, [datetime(2026, 11, 6, 17, 30, 0)]),
    ({"hasta": HASTA}, [datetime(2026, 11, 8, 23, 59, 59)]),
    ({"local_id": "2"}, [2]),
])
@pytest.mark.parametrize("ruta", RUTAS)
def test_cada_filtro_se_aplica_solo_por_separado(cliente_backend, cabeceras, bd, ruta, filtros, esperado):
    cliente_backend.get(ruta, query_string=filtros, headers=cabeceras)
    for sql, parametros in _consultas(bd):
        assert parametros == esperado
        assert sql.count("%s") == 1


def test_cancelaciones_aplica_los_tres_filtros_en_ambos_select(cliente_backend, cabeceras, bd):
    cliente_backend.get(CANCELACIONES, query_string={"desde": DESDE, "hasta": HASTA, "local_id": "1"},
                        headers=cabeceras)
    consultas = _consultas(bd)
    assert len(consultas) == 2
    for sql, parametros in consultas:
        assert len(parametros) == sql.count("%s") == 3
        assert parametros.index(datetime(2026, 11, 6, 17, 30, 0)) < parametros.index(datetime(2026, 11, 8, 23, 59, 59))
        assert parametros.count(1) == 1 and type(parametros[parametros.index(1)]) is int
        assert re.search(r"local_id\s*=\s*%s", sql)


def test_franjas_horarias_filtra_por_local_de_la_sala(cliente_backend, cabeceras, bd):
    cliente_backend.get(FRANJAS, query_string={"local_id": "2"}, headers=cabeceras)
    (sql, _), = _consultas(bd)
    assert re.search(r"local_id\s*=\s*%s", sql)


# filtros: construir_filtros (recibe los textos de la URL, valida y arma las condiciones)
def test_construir_filtros_sin_valores_no_agrega_nada():
    clausulas, parametros = construir_filtros()
    assert not clausulas and not parametros


def test_construir_filtros_con_los_tres_valores_arma_una_condicion_por_parametro(app_backend):
    clausulas, parametros = construir_filtros(DESDE, HASTA, "3")
    assert list(parametros) == [datetime(2026, 11, 6, 17, 30, 0), datetime(2026, 11, 8, 23, 59, 59), 3]
    assert clausulas.count("%s") == 3
    assert clausulas.index(">=") < clausulas.index("<=") < clausulas.index("local_id")
    assert "2026" not in clausulas  # los valores van como parámetros, no pegados al SQL


@pytest.mark.parametrize("filtros, esperado", [
    ({"desde": DESDE}, [datetime(2026, 11, 6, 17, 30, 0)]),
    ({"hasta": HASTA}, [datetime(2026, 11, 8, 23, 59, 59)]),
    ({"local_id": "5"}, [5]),
])
def test_construir_filtros_con_un_solo_valor_arma_una_sola_condicion(app_backend, filtros, esperado):
    clausulas, parametros = construir_filtros(**filtros)
    assert list(parametros) == esperado
    assert clausulas.count("%s") == 1


@pytest.mark.parametrize("filtros", [{"desde": ""}, {"hasta": "2026-11-06"}, {"local_id": ""}, {"local_id": "0"},
                                     {"desde": HASTA, "hasta": DESDE}])
def test_construir_filtros_invalidos_cortan_con_400(app_backend, filtros):
    with pytest.raises(HTTPException) as error:
        construir_filtros(**filtros)
    assert error.value.response.status_code == 400
    assert error.value.response.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"


# SQL: agrupación, orden, estados y conteos
def test_franjas_horarias_agrupa_por_bloque_de_dos_horas_y_ordena(cliente_backend, cabeceras, bd):
    cliente_backend.get(FRANJAS, headers=cabeceras)
    (sql, parametros), = _consultas(bd)
    assert "GROUP BY" in sql.upper()
    assert "HOUR(" in sql.upper()
    # entradas descendente y, en caso de empate, hora_desde ascendente
    descendente, desempate = _orden(sql).split("DESC", 1)
    assert "," in desempate and ("HORA" in desempate or "HOUR" in desempate)


def test_franjas_horarias_cuenta_entradas_activas_solo_de_compras_confirmadas(cliente_backend, cabeceras, bd):
    cliente_backend.get(FRANJAS, headers=cabeceras)
    (sql, parametros), = _consultas(bd)
    texto = _sql_y_valores(sql, parametros)
    assert "confirmada" in texto
    for estado in ("pendiente", "vencida", "cancelada"):
        assert estado not in texto
    assert "entradas" in texto and "activa" in texto
    # sin JOIN a servicios, que multiplicaría las entradas de una compra por sus servicios
    assert "servicios" not in texto


def test_cancelaciones_cuenta_compras_confirmadas_y_canceladas_sin_pendientes_ni_vencidas(
        cliente_backend, cabeceras, bd):
    cliente_backend.get(CANCELACIONES, headers=cabeceras)
    consultas = _consultas(bd)
    assert len(consultas) == 2
    for sql, parametros in consultas:
        texto = _sql_y_valores(sql, parametros)
        assert "confirmada" in texto and "cancelada" in texto
        assert "pendiente" not in texto and "vencida" not in texto
        assert "GROUP BY" in sql.upper()


def test_cancelaciones_no_une_entradas_ni_servicios_para_no_multiplicar_compras(cliente_backend, cabeceras, bd):
    cliente_backend.get(CANCELACIONES, headers=cabeceras)
    for sql, parametros in _consultas(bd):
        texto = _sql_y_valores(sql, parametros)
        assert "entradas" not in texto and "servicios" not in texto


def test_cancelaciones_ordena_peliculas_por_canceladas_y_periodos_cronologicamente(cliente_backend, cabeceras, bd):
    cliente_backend.get(CANCELACIONES, headers=cabeceras)
    por_pelicula, por_periodo = sorted(_consultas(bd), key=lambda consulta: "periodo" in consulta[0].lower())
    descendente, desempate = _orden(por_pelicula[0]).split("DESC", 1)  # canceladas DESC, pelicula_id
    assert "," in desempate
    assert "DESC" not in _orden(por_periodo[0])
    assert "fecha_hora" in por_periodo[0].lower() or "periodo" in _orden(por_periodo[0]).lower()


# validación: 400 sin consultar
FORMATOS_INVALIDOS = ["", " ", "ayer", "2026-11-06", "2026-11-06T10:00", "2026-11-06 10:00:00",
                      "2026-11-06T10:00:00Z", "2026-11-06T10:00:00+00:00", "2026-11-06T10:00:00.000",
                      "20261106T100000", "2026-1-6T1:2:3", "2026-13-01T00:00:00", "2026-02-30T00:00:00",
                      "2026-11-06T24:00:00", "2026-11-06T10:60:00"]


@pytest.mark.parametrize("valor", FORMATOS_INVALIDOS)
@pytest.mark.parametrize("campo", ["desde", "hasta"])
@pytest.mark.parametrize("ruta", RUTAS)
def test_fecha_invalida_devuelve_400_sin_consultar(cliente_backend, cabeceras, bd, ruta, campo, valor):
    respuesta = cliente_backend.get(ruta, query_string={campo: valor}, headers=cabeceras)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    bd.assert_not_called()


@pytest.mark.parametrize("valor", ["", " ", "0", "-1", "abc", "1.5", "1e2", "1,2", "3 4", "0x3", "1" * 19])
@pytest.mark.parametrize("ruta", RUTAS)
def test_local_id_invalido_devuelve_400_sin_consultar(cliente_backend, cabeceras, bd, ruta, valor):
    respuesta = cliente_backend.get(ruta, query_string={"local_id": valor}, headers=cabeceras)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    bd.assert_not_called()


@pytest.mark.parametrize("ruta", RUTAS)
def test_rango_invertido_devuelve_400_sin_consultar(cliente_backend, cabeceras, bd, ruta):
    filtros = {"desde": "2026-11-08T00:00:01", "hasta": "2026-11-08T00:00:00"}
    respuesta = cliente_backend.get(ruta, query_string=filtros, headers=cabeceras)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "DATOS_INVALIDOS"
    bd.assert_not_called()


@pytest.mark.parametrize("ruta", RUTAS)
def test_desde_igual_a_hasta_es_un_rango_valido(cliente_backend, cabeceras, bd, ruta):
    instante = "2026-11-08T21:00:00"
    respuesta = cliente_backend.get(ruta, query_string={"desde": instante, "hasta": instante}, headers=cabeceras)
    assert respuesta.status_code == 200
    for _, parametros in _consultas(bd):
        assert parametros == [datetime(2026, 11, 8, 21, 0, 0)] * 2


# --- backend: ocupación y ventas por género (SCRUM-75) ---
FILA_OCUPACION_PELICULA = {"pelicula_id": 5, "pelicula": "El viaje de Chihiro", "vendidas": Decimal("2"),
                           "capacidad": Decimal("192"), "ocupacion": Decimal("1.04")}
FILA_OCUPACION_FUNCION = {"funcion_id": 9, "pelicula": "El viaje de Chihiro", "local": "Centro", "sala": "Sala 1",
                          "fecha_hora": datetime(2026, 11, 7, 21, 0, 0), "vendidas": 2, "capacidad": 96,
                          "ocupacion": Decimal("2.08")}
FILA_VENTAS_GENERO = {"genero": "Animación", "entradas": 3, "monto": Decimal("16500.00")}


def _filas_de_ocupacion(sql, parametros=None):
    return [FILA_OCUPACION_FUNCION] if "funcion_id" in sql.split("FROM")[0] else [FILA_OCUPACION_PELICULA]


def test_ocupacion_devuelve_200_con_numeros_y_fecha_iso(cliente_backend, cabeceras, bd):
    bd.side_effect = _filas_de_ocupacion
    respuesta = cliente_backend.get(OCUPACION, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "por_pelicula": [{"pelicula_id": 5, "pelicula": "El viaje de Chihiro", "vendidas": 2, "capacidad": 192,
                          "ocupacion": 1.04}],
        "por_funcion": [{"funcion_id": 9, "pelicula": "El viaje de Chihiro", "local": "Centro", "sala": "Sala 1",
                         "fecha_hora": "2026-11-07T21:00:00", "vendidas": 2, "capacidad": 96, "ocupacion": 2.08}],
    }


def test_ocupacion_sin_funciones_devuelve_las_dos_listas_vacias(cliente_backend, cabeceras, bd):
    respuesta = cliente_backend.get(OCUPACION, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"por_pelicula": [], "por_funcion": []}


def test_ocupacion_parte_de_funciones_y_cuenta_las_vendidas_aparte(cliente_backend, cabeceras, bd):
    cliente_backend.get(OCUPACION, headers=cabeceras)
    por_pelicula, por_funcion = (sql for sql, _ in _consultas(bd))
    for sql in (por_pelicula, por_funcion):
        assert "FROM funciones f" in sql
        assert re.search(r"LEFT JOIN \(SELECT e\.funcion_id, COUNT\(\*\).*GROUP BY e\.funcion_id\) v", sql)
        assert "c.estado = 'confirmada' AND e.activa = 1" in sql
    assert "GROUP BY p.id, p.titulo" in por_pelicula


def test_ventas_genero_devuelve_200_con_numeros(cliente_backend, cabeceras, bd):
    bd.return_value = [FILA_VENTAS_GENERO]
    respuesta = cliente_backend.get(VENTAS_GENERO, headers=cabeceras)
    datos = respuesta.get_json()
    assert respuesta.status_code == 200
    assert datos == [{"genero": "Animación", "entradas": 3, "monto": 16500.0}]
    assert isinstance(datos[0]["monto"], float)


def test_ventas_genero_sin_ventas_devuelve_lista_vacia(cliente_backend, cabeceras, bd):
    respuesta = cliente_backend.get(VENTAS_GENERO, headers=cabeceras)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == []


def test_ventas_genero_agrupa_por_primer_genero_y_suma_precio_de_entradas(cliente_backend, cabeceras, bd):
    cliente_backend.get(VENTAS_GENERO, headers=cabeceras)
    (sql, _), = _consultas(bd)
    assert "GROUP BY SUBSTRING_INDEX(p.genero, ',', 1)" in sql
    assert "SUM(e.precio)" in sql and "c.total" not in sql
    assert "c.estado = 'confirmada' AND e.activa = 1" in sql
