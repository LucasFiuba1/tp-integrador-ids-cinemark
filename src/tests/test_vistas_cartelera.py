"""Pruebas de las vistas de cartelera y detalle de película (SCRUM-59).

El contexto que las rutas le pasan a los templates se verifica reemplazando render_template; el HTML se prueba
con el render real solo donde importa (header y 404).
"""
from unittest.mock import patch

import pytest

ERROR_BACKEND = {"status": 503, "codigo": "BACKEND_NO_DISPONIBLE", "mensaje": "No se pudo conectar con el servidor."}

CARTELERA = [
    {"id": 3, "titulo": "Volver al futuro", "poster_url": None, "duracion_min": 116,
     "clasificacion": "ATP", "genero": "Ciencia ficción", "proxima_funcion": "2026-11-10T18:00:00"},
    {"id": 7, "titulo": "Cinema Paradiso", "poster_url": "https://img.test/p.jpg", "duracion_min": 124,
     "clasificacion": "+13", "genero": "Drama", "proxima_funcion": "2026-11-11T20:00:00"},
]

PELICULA = {
    "id": 3, "titulo": "Volver al futuro", "sinopsis": "Un viaje en el tiempo.",
    "poster_url": None, "duracion_min": 116, "clasificacion": "ATP", "genero": "Ciencia ficción",
    "funciones": [
        {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "precio": 5500.0,
         "nombre_sala": "Sala 1", "nombre_local": "Paradiso Centro"},
        {"id": 13, "fecha_hora": "2026-11-11T18:00:00", "precio": 5500.0,
         "nombre_sala": "Sala 1", "nombre_local": "Paradiso Belgrano"},
        {"id": 14, "fecha_hora": "2026-11-10T22:00:00", "precio": 6000.0,
         "nombre_sala": "Sala 2", "nombre_local": "Paradiso Centro"},
        {"id": 15, "fecha_hora": "2026-11-10T16:00:00", "precio": 5000.0,
         "nombre_sala": "Sala 3", "nombre_local": "Paradiso Belgrano"},
    ],
}


@pytest.fixture
def llamar():
    with patch("src.frontend.routes.publico.llamar") as llamar:
        yield llamar


@pytest.fixture
def contexto():
    """Reemplaza render_template y deja en el dict el template y el contexto con que se lo llamó."""
    llamada = {}

    def renderizar(plantilla, **datos):
        llamada.update(datos, plantilla=plantilla)
        return "pagina"

    with patch("src.frontend.routes.publico.render_template", side_effect=renderizar):
        yield llamada


def _flashes(cliente):
    with cliente.session_transaction() as sesion:
        return [mensaje for _, mensaje in sesion.get("_flashes", [])]


def _ids_funciones(contexto):
    return [funcion["id"] for funcion in contexto["pelicula"]["funciones"]]


# --- Cartelera (inicio) ---------------------------------------------------------------------------------------


def test_cartelera_sin_filtros_llama_solo_a_la_cartelera_y_no_a_salud(cliente_frontend, llamar, contexto):
    llamar.return_value = (list(CARTELERA), None)
    respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    llamar.assert_called_once_with("GET", "/api/cartelera", params=None)
    assert contexto["plantilla"] == "inicio.html"
    assert "estado_api" not in contexto
    assert contexto["peliculas"] == CARTELERA
    assert contexto["local_id"] == "" and contexto["fecha"] == "" and contexto["pelicula_id"] == ""
    assert contexto["error_cartelera"] is False


def test_cartelera_envia_local_y_fecha_a_la_api(cliente_frontend, llamar, contexto):
    llamar.return_value = ([], None)
    cliente_frontend.get("/?local_id=2&fecha=2026-11-10")
    llamar.assert_called_once_with("GET", "/api/cartelera", params={"local_id": "2", "fecha": "2026-11-10"})
    assert contexto["local_id"] == "2" and contexto["fecha"] == "2026-11-10"


def test_cartelera_no_envia_la_pelicula_a_la_api(cliente_frontend, llamar, contexto):
    llamar.return_value = (list(CARTELERA), None)
    cliente_frontend.get("/?local_id=1&pelicula_id=7")
    llamar.assert_called_once_with("GET", "/api/cartelera", params={"local_id": "1"})


def test_cartelera_ofrece_locales_del_seed_y_peliculas_para_el_header(cliente_frontend, llamar, contexto):
    llamar.return_value = (list(CARTELERA), None)
    cliente_frontend.get("/")
    assert contexto["header_locales"] == [
        {"valor": "1", "texto": "Paradiso Centro"},
        {"valor": "2", "texto": "Paradiso Belgrano"},
        {"valor": "3", "texto": "Paradiso Palermo"},
    ]
    assert contexto["header_peliculas"] == [
        {"valor": "3", "texto": "Volver al futuro"},
        {"valor": "7", "texto": "Cinema Paradiso"},
    ]
    assert {"valor": "", "texto": "Todos"} in contexto["locales"]


def test_cartelera_header_mantiene_la_seleccion_del_get(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = cliente_frontend.get("/?local_id=2&pelicula_id=7").get_data(as_text=True)
    assert '<option value="2" selected>Paradiso Belgrano</option>' in html
    assert '<option value="7" selected>Cinema Paradiso</option>' in html
    assert '<option value="3">Volver al futuro</option>' in html


def test_cartelera_con_pelicula_elegida_filtra_en_python_y_conserva_el_catalogo(cliente_frontend, llamar, contexto):
    llamar.return_value = (list(CARTELERA), None)
    cliente_frontend.get("/?pelicula_id=7")
    assert [pelicula["id"] for pelicula in contexto["peliculas"]] == [7]
    assert contexto["pelicula_id"] == "7"
    assert len(contexto["header_peliculas"]) == 2
    assert contexto["error_cartelera"] is False


def test_cartelera_con_pelicula_fuera_de_los_resultados_queda_vacia_sin_error(cliente_frontend, llamar, contexto):
    llamar.return_value = (list(CARTELERA), None)
    cliente_frontend.get("/?pelicula_id=99")
    assert contexto["peliculas"] == []
    assert contexto["pelicula_id"] == "99"
    assert contexto["error_cartelera"] is False
    assert _flashes(cliente_frontend) == []


@pytest.mark.parametrize("pelicula_id", ["abc", "-1", "0", "²", "1.5", " ", "3; DROP"])
def test_cartelera_con_pelicula_id_invalido_lo_ignora_sin_romper(cliente_frontend, llamar, contexto, pelicula_id):
    llamar.return_value = (list(CARTELERA), None)
    respuesta = cliente_frontend.get("/", query_string={"pelicula_id": pelicula_id})
    assert respuesta.status_code == 200
    assert contexto["peliculas"] == CARTELERA
    assert contexto["pelicula_id"] == ""


def test_cartelera_con_api_caida_avisa_y_diferencia_el_error_de_la_lista_vacia(cliente_frontend, llamar, contexto):
    llamar.return_value = (None, ERROR_BACKEND)
    respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    assert contexto["peliculas"] == []
    assert contexto["error_cartelera"] is True
    assert contexto["header_peliculas"] == []
    assert _flashes(cliente_frontend) == ["No se pudo conectar con el servidor."]


def test_cartelera_con_filtro_rechazado_por_el_backend_muestra_su_mensaje(cliente_frontend, llamar, contexto):
    error = {"status": 400, "codigo": "DATOS_INVALIDOS", "mensaje": "fecha debe tener formato YYYY-MM-DD."}
    llamar.return_value = (None, error)
    respuesta = cliente_frontend.get("/?fecha=ayer")
    assert respuesta.status_code == 200
    assert contexto["error_cartelera"] is True
    assert contexto["fecha"] == "ayer"
    assert _flashes(cliente_frontend) == ["fecha debe tener formato YYYY-MM-DD."]


def test_cartelera_sin_funciones_es_lista_vacia_y_no_error(cliente_frontend, llamar, contexto):
    llamar.return_value = ([], None)
    cliente_frontend.get("/?local_id=3")
    assert contexto["peliculas"] == []
    assert contexto["error_cartelera"] is False
    assert _flashes(cliente_frontend) == []


def test_cartelera_con_respuesta_vacia_del_backend_no_muestra_none(cliente_frontend, llamar):
    llamar.return_value = (None, None)
    respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    assert "None" not in respuesta.get_data(as_text=True)


@pytest.mark.parametrize("datos", [None, {}, "texto", 5, {"estado": "ok"}])
def test_cartelera_con_payload_inesperado_no_rompe_y_avisa(cliente_frontend, llamar, contexto, datos):
    llamar.return_value = (datos, None)
    respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    assert contexto["peliculas"] == []
    assert contexto["error_cartelera"] is True
    assert len(_flashes(cliente_frontend)) == 1


def test_cartelera_ignora_elementos_inesperados_de_la_lista(cliente_frontend, llamar, contexto):
    llamar.return_value = ([None, 4, {"titulo": "Sin id"}, CARTELERA[0]], None)
    respuesta = cliente_frontend.get("/")
    assert respuesta.status_code == 200
    assert contexto["peliculas"] == [CARTELERA[0]]
    assert contexto["header_peliculas"] == [{"valor": "3", "texto": "Volver al futuro"}]


def test_cartelera_con_pelicula_sin_titulo_usa_un_texto_en_el_header(cliente_frontend, llamar, contexto):
    llamar.return_value = ([{"id": 9, "titulo": None}], None)
    cliente_frontend.get("/")
    assert contexto["header_peliculas"] == [{"valor": "9", "texto": "Película 9"}]


# --- Detalle de película --------------------------------------------------------------------------------------


def test_detalle_llama_una_sola_vez_y_ordena_funciones_por_local_y_fecha(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    respuesta = cliente_frontend.get("/peliculas/3")
    assert respuesta.status_code == 200
    llamar.assert_called_once_with("GET", "/api/peliculas/3")
    assert contexto["plantilla"] == "pelicula.html"
    assert _ids_funciones(contexto) == [15, 13, 12, 14]
    assert contexto["total_funciones"] == 4
    assert contexto["filtro_activo"] is False
    assert contexto["errores_filtro"] == {}
    assert contexto["local_id"] == "" and contexto["fecha"] == ""


def test_detalle_ofrece_catalogos_para_el_header(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    cliente_frontend.get("/peliculas/3")
    assert [local["valor"] for local in contexto["header_locales"]] == ["1", "2", "3"]
    assert contexto["header_peliculas"] == [{"valor": "3", "texto": "Volver al futuro"}]
    assert {"valor": "", "texto": "Todos"} in contexto["locales"]


def test_detalle_filtra_funciones_por_local(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    cliente_frontend.get("/peliculas/3?local_id=1")
    assert _ids_funciones(contexto) == [12, 14]
    assert contexto["local_id"] == "1"
    assert contexto["filtro_activo"] is True
    assert contexto["total_funciones"] == 4


def test_detalle_filtra_funciones_por_fecha(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    cliente_frontend.get("/peliculas/3?fecha=2026-11-11")
    assert _ids_funciones(contexto) == [13]
    assert contexto["fecha"] == "2026-11-11"


def test_detalle_combina_local_y_fecha_y_conserva_el_orden(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    cliente_frontend.get("/peliculas/3?local_id=2&fecha=2026-11-10")
    assert _ids_funciones(contexto) == [15]
    cliente_frontend.get("/peliculas/3?local_id=1&fecha=2026-11-10")
    assert _ids_funciones(contexto) == [12, 14]


def test_detalle_con_filtro_sin_resultados_diferencia_de_pelicula_sin_funciones(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    cliente_frontend.get("/peliculas/3?local_id=3")
    assert contexto["pelicula"]["funciones"] == []
    assert contexto["filtro_activo"] is True
    assert contexto["total_funciones"] == 4
    assert contexto["errores_filtro"] == {}


def test_detalle_de_pelicula_sin_funciones_no_tiene_total(cliente_frontend, llamar, contexto):
    llamar.return_value = ({**PELICULA, "funciones": []}, None)
    cliente_frontend.get("/peliculas/3")
    assert contexto["pelicula"]["funciones"] == []
    assert contexto["total_funciones"] == 0
    assert contexto["filtro_activo"] is False


@pytest.mark.parametrize("local_id", ["99", "abc", "0", "-1", "²", "1 OR 1=1"])
def test_detalle_con_local_invalido_avisa_y_muestra_todas_las_funciones(cliente_frontend, llamar, contexto, local_id):
    llamar.return_value = (dict(PELICULA), None)
    respuesta = cliente_frontend.get("/peliculas/3", query_string={"local_id": local_id})
    assert respuesta.status_code == 200
    assert list(contexto["errores_filtro"]) == ["local_id"]
    assert "local" in contexto["errores_filtro"]["local_id"]
    assert "todos los locales" in contexto["errores_filtro"]["local_id"]
    assert contexto["local_id"] == ""
    assert contexto["filtro_activo"] is False
    assert _ids_funciones(contexto) == [15, 13, 12, 14]


@pytest.mark.parametrize("fecha", ["ayer", "2026-13-01", "2026-02-30", "2026-1-5", "20261110", "2026-11-10T20:00:00"])
def test_detalle_con_fecha_invalida_avisa_y_muestra_todas_las_funciones(cliente_frontend, llamar, contexto, fecha):
    llamar.return_value = (dict(PELICULA), None)
    respuesta = cliente_frontend.get("/peliculas/3", query_string={"fecha": fecha})
    assert respuesta.status_code == 200
    assert list(contexto["errores_filtro"]) == ["fecha"]
    assert "AAAA-MM-DD" in contexto["errores_filtro"]["fecha"]
    assert contexto["fecha"] == ""
    assert _ids_funciones(contexto) == [15, 13, 12, 14]


def test_detalle_con_un_filtro_valido_y_otro_invalido_aplica_solo_el_valido(cliente_frontend, llamar, contexto):
    llamar.return_value = (dict(PELICULA), None)
    cliente_frontend.get("/peliculas/3?local_id=1&fecha=nunca")
    assert list(contexto["errores_filtro"]) == ["fecha"]
    assert contexto["local_id"] == "1"
    assert _ids_funciones(contexto) == [12, 14]


def test_detalle_con_funciones_inesperadas_no_rompe(cliente_frontend, llamar, contexto):
    pelicula = {**PELICULA, "funciones": [None, "x", {"id": 1, "fecha_hora": None, "nombre_local": None}, PELICULA["funciones"][0]]}
    llamar.return_value = (pelicula, None)
    respuesta = cliente_frontend.get("/peliculas/3?fecha=2026-11-10")
    assert respuesta.status_code == 200
    assert _ids_funciones(contexto) == [12]
    assert contexto["total_funciones"] == 2


@pytest.mark.parametrize("funciones", [None, "texto", {"id": 1}])
def test_detalle_con_funciones_que_no_son_lista_las_trata_como_vacias(cliente_frontend, llamar, contexto, funciones):
    llamar.return_value = ({**PELICULA, "funciones": funciones}, None)
    respuesta = cliente_frontend.get("/peliculas/3")
    assert respuesta.status_code == 200
    assert contexto["pelicula"]["funciones"] == []
    assert contexto["total_funciones"] == 0


def test_detalle_con_payload_que_no_es_pelicula_redirige_con_aviso(cliente_frontend, llamar):
    llamar.return_value = (None, None)
    respuesta = cliente_frontend.get("/peliculas/3")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    assert len(_flashes(cliente_frontend)) == 1


def test_detalle_de_pelicula_inexistente_muestra_404_amigable(cliente_frontend, llamar):
    llamar.return_value = (None, {"status": 404, "codigo": "NO_ENCONTRADO", "mensaje": "La película no existe."})
    respuesta = cliente_frontend.get("/peliculas/99?local_id=1")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 404
    assert "No encontramos esa página" in html
    assert 'href="/">cartelera</a>' in html
    llamar.assert_called_once_with("GET", "/api/peliculas/99")


def test_detalle_con_backend_caido_vuelve_a_la_cartelera_con_aviso(cliente_frontend, llamar):
    llamar.return_value = (None, ERROR_BACKEND)
    respuesta = cliente_frontend.get("/peliculas/3")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_frontend) == ["No se pudo conectar con el servidor."]
    llamar.assert_called_once_with("GET", "/api/peliculas/3")


def test_detalle_con_id_que_no_es_numero_devuelve_404(cliente_frontend, llamar):
    assert cliente_frontend.get("/peliculas/abc").status_code == 404
    llamar.assert_not_called()
