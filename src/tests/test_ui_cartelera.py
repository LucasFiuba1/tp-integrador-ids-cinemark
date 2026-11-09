"""Pruebas del HTML de la cartelera y del detalle de película (SCRUM-59, Figma 23:280 / 26:1187 y 23:542 / 26:1382).

Renderizan los templates reales con la API simulada: tarjetas y póster compartido, filtros GET con campo/filtro,
datos en none que no se muestran, la elección de función con chip_funcion + "Elegir butacas" (sin JS) y los dos
formularios GET (header y filtros), que conservan el parámetro del otro como campo oculto.
"""
import re
from unittest.mock import patch

import pytest

CARTELERA = [
    {"id": 1, "titulo": "Volver al futuro", "poster_url": None, "duracion_min": 116, "clasificacion": "ATP",
     "genero": "Aventura", "proxima_funcion": "2026-11-10T18:00:00"},
    {"id": 2, "titulo": "El padrino", "poster_url": "https://img.test/padrino.jpg", "duracion_min": 175,
     "clasificacion": "+16", "genero": "Drama", "proxima_funcion": "2026-11-11T20:00:00"},
]

PELICULA = {
    "id": 1, "titulo": "Volver al futuro", "sinopsis": "Un viaje en el tiempo.", "poster_url": None,
    "duracion_min": 116, "clasificacion": "ATP", "genero": "Aventura", "disponible_hasta": "2026-11-30T23:59:59",
    "funciones": [
        {"id": 12, "fecha_hora": "2026-11-10T20:30:00", "precio": 5500.0, "nombre_sala": "Sala 1",
         "nombre_local": "Paradiso Centro"},
        {"id": 13, "fecha_hora": "2026-11-10T22:15:00", "precio": 5500.0, "nombre_sala": "Sala 2",
         "nombre_local": "Paradiso Centro"},
        {"id": 14, "fecha_hora": "2026-11-10T17:30:00", "precio": 6000.0, "nombre_sala": "Sala 1",
         "nombre_local": "Paradiso Belgrano"},
    ],
}


@pytest.fixture
def llamar():
    with patch("src.frontend.routes.publico.llamar") as llamar:
        yield llamar


def _html(cliente, url):
    respuesta = cliente.get(url)
    assert respuesta.status_code == 200
    return respuesta.get_data(as_text=True)


# --- Cartelera ------------------------------------------------------------------------------------------------


def test_cartelera_muestra_tarjetas_en_lista_con_link_al_detalle(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/")
    assert '<ul class="grilla-peliculas" role="list">' in html
    assert html.count('<article class="tarjeta-pelicula">') == 2
    assert '<a href="/peliculas/1">Volver al futuro</a>' in html
    assert "1h 56m" in html and "2h 55m" in html
    assert 'class="badge badge-clasificacion">ATP</span>' in html
    # Sin póster: degradé con el título, oculto a lectores porque el título ya está en la tarjeta.
    assert 'class="poster poster-vacio poster-tono-1" aria-hidden="true"' in html
    assert 'src="https://img.test/padrino.jpg"' in html and 'alt=""' in html
    assert "Estado de la API" not in html


def test_cartelera_destaca_la_primera_pelicula(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/")
    assert 'class="destacada-titulo" id="destacada-titulo">Volver al futuro</h2>' in html
    assert "Próxima función · 10/11 · 18:00" in html
    assert ">Comprar entradas</a>" in html


def test_cartelera_filtros_get_con_campo_y_filtro_reusables(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/?local_id=2&fecha=2026-11-10")
    assert '<form method="get" action="/" class="filtros-cartelera"' in html
    assert '<label class="filtro">' in html and '<select name="local_id">' in html
    assert '<label class="campo">' in html and '<input type="date" name="fecha" value="2026-11-10">' in html
    assert "<strong>Paradiso Belgrano</strong>" in html and "<strong>10/11/2026</strong>" in html
    # Las tarjetas llevan los filtros al detalle; el header sigue siendo el único formulario "selectores".
    assert 'href="/peliculas/1?local_id=2&amp;fecha=2026-11-10"' in html
    assert html.count('class="selectores"') == 1
    assert ">Limpiar filtros</a>" in html


def test_cartelera_con_datos_en_none_no_los_muestra(cliente_frontend, llamar):
    llamar.return_value = ([{"id": 5, "titulo": None, "poster_url": None, "duracion_min": None,
                             "clasificacion": None, "genero": None, "proxima_funcion": None}], None)
    html = _html(cliente_frontend, "/")
    assert "None" not in html
    assert "Película sin título" in html
    assert "badge-clasificacion" not in html and "tarjeta-pelicula-duracion" not in html


def test_cartelera_caida_muestra_estado_propio_sin_repetir_el_aviso(cliente_frontend, llamar):
    llamar.return_value = (None, {"status": 503, "codigo": "BACKEND_NO_DISPONIBLE",
                                  "mensaje": "No se pudo conectar con el servidor."})
    html = _html(cliente_frontend, "/")
    assert html.count("No se pudo conectar con el servidor.") == 1
    assert "La cartelera no se pudo cargar." in html and ">Reintentar</a>" in html


def test_cartelera_vacia_con_y_sin_filtros(cliente_frontend, llamar):
    llamar.return_value = ([], None)
    assert "no hay funciones disponibles en cartelera" in _html(cliente_frontend, "/")
    assert "No hay funciones para los filtros que elegiste." in _html(cliente_frontend, "/?local_id=3")


# --- Detalle --------------------------------------------------------------------------------------------------


def test_detalle_muestra_datos_y_funciones_agrupadas_por_local(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    html = _html(cliente_frontend, "/peliculas/1")
    assert '<h1 class="pelicula-titulo">Volver al futuro</h1>' in html
    assert "Un viaje en el tiempo." in html
    for dato in ("<dt>Duración</dt><dd>1h 56m</dd>", "<dt>Clasificación</dt><dd>ATP</dd>",
                 "<dt>Género</dt><dd>Aventura</dd>", "<dt>Disponible hasta</dt><dd>30/11/2026</dd>"):
        assert dato in html
    assert 'role="img" aria-label="Volver al futuro (sin póster)"' in html
    assert html.index(">Paradiso Belgrano</h3>") < html.index(">Paradiso Centro</h3>")
    assert html.count('class="chip-funcion"') == 3
    assert "Sala 1 · $5.500" in html


def test_detalle_elige_funcion_con_radios_y_un_boton_por_funcion(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    html = _html(cliente_frontend, "/peliculas/1")
    assert html.count('type="radio" name="funcion"') == 3
    assert html.count(" checked>") == 1  # la primera llega elegida: siempre hay un botón visible
    assert html.count(">Elegir butacas</a>") == 3
    for funcion_id in (12, 13, 14):
        assert f'href="/funciones/{funcion_id}/butacas"' in html
    assert "<script" not in html


def test_detalle_con_datos_en_none_no_los_muestra(cliente_frontend, llamar):
    llamar.return_value = ({**PELICULA, "sinopsis": None, "clasificacion": None, "genero": None,
                            "duracion_min": None, "disponible_hasta": None}, None)
    html = _html(cliente_frontend, "/peliculas/1")
    assert "None" not in html
    assert "pelicula-sinopsis" not in html and "pelicula-datos" not in html


def test_detalle_conserva_filtros_y_muestra_errores_en_los_campos(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    html = _html(cliente_frontend, "/peliculas/1?local_id=99&fecha=ayer")
    assert '<label class="filtro campo-invalido">' in html
    assert 'aria-describedby="error-local_id"' in html and 'aria-describedby="error-fecha"' in html
    assert "No reconocemos ese local." in html and "AAAA-MM-DD" in html

    html = _html(cliente_frontend, "/peliculas/1?local_id=1&fecha=2026-11-10")
    assert '<a href="/?local_id=1&amp;fecha=2026-11-10">Cartelera</a>' in html
    assert '<input type="date" name="fecha" value="2026-11-10">' in html
    assert ">Ver todas</a>" in html


def test_detalle_filtrado_sin_resultados_ofrece_ver_todas(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    html = _html(cliente_frontend, "/peliculas/1?local_id=3")
    assert "No hay funciones para ese local o fecha." in html
    assert "Ver las 3 funciones" in html


def test_detalle_sin_funciones_y_aviso_de_sesion(cliente_frontend, llamar):
    llamar.return_value = ({**PELICULA, "funciones": []}, None)
    html = _html(cliente_frontend, "/peliculas/1")
    assert "No hay funciones programadas" in html
    assert "Necesitás iniciar sesión para comprar." in html


# --- Formularios GET: cada uno conserva el filtro que no edita, sin repetir names -----------------------------


def _formulario(html, clase):
    return re.search(rf'<form method="get"[^>]*class="{clase}[^"]*".*?</form>', html, re.S).group(0)


def _names(formulario):
    return re.findall(r'name="([^"]+)"', formulario)


def test_header_y_filtro_de_la_cartelera_conservan_el_parametro_del_otro(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/?local_id=2&fecha=2026-11-10&pelicula_id=1")
    header = _formulario(html, "selectores")
    filtros = _formulario(html, "filtros-cartelera")
    assert '<input type="hidden" name="fecha" value="2026-11-10">' in header
    assert '<input type="hidden" name="pelicula_id" value="1">' in filtros
    assert sorted(_names(header)) == ["fecha", "local_id", "pelicula_id"]
    assert sorted(_names(filtros)) == ["fecha", "local_id", "pelicula_id"]
    assert 'type="hidden" name="local_id"' not in header + filtros


def test_formularios_sin_filtros_no_agregan_ocultos(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/")
    assert 'type="hidden"' not in _formulario(html, "selectores") + _formulario(html, "filtros-cartelera")


def test_tarjetas_llevan_local_y_fecha_pero_no_la_pelicula(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/?local_id=1&fecha=2026-11-10&pelicula_id=2")
    assert '<a href="/peliculas/2?local_id=1&amp;fecha=2026-11-10">El padrino</a>' in html
    assert "/peliculas/2?pelicula_id" not in html and "&amp;pelicula_id" not in html


def test_detalle_header_conserva_solo_filtros_validos(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    header = _formulario(_html(cliente_frontend, "/peliculas/1?local_id=2&fecha=2026-11-10"), "selectores")
    assert '<input type="hidden" name="fecha" value="2026-11-10">' in header
    assert '<option value="2" selected>Paradiso Belgrano</option>' in header
    # Una fecha inválida se descarta en la ruta: el header no la arrastra a la cartelera.
    header = _formulario(_html(cliente_frontend, "/peliculas/1?fecha=ayer"), "selectores")
    assert 'name="fecha"' not in header


def test_detalle_filtro_no_necesita_la_pelicula(cliente_frontend, llamar):
    llamar.return_value = (dict(PELICULA), None)
    filtros = _formulario(_html(cliente_frontend, "/peliculas/1?local_id=1"), "filtros-cartelera")
    assert 'action="/peliculas/1"' in filtros
    assert sorted(_names(filtros)) == ["fecha", "local_id"]


# --- Póster, títulos y meta ----------------------------------------------------------------------------------


def test_detalle_con_poster_real_usa_alt_descriptivo(cliente_frontend, llamar):
    llamar.return_value = ({**PELICULA, "poster_url": "https://img.test/vaf.jpg"}, None)
    html = _html(cliente_frontend, "/peliculas/1")
    assert 'src="https://img.test/vaf.jpg"' in html and 'alt="Póster de Volver al futuro"' in html
    assert "<title>Volver al futuro · Cine Paradiso</title>" in html


def test_tarjeta_muestra_titulo_genero_y_duracion_accesible(cliente_frontend, llamar):
    llamar.return_value = (list(CARTELERA), None)
    html = _html(cliente_frontend, "/")
    assert '<p class="tarjeta-pelicula-genero">Drama</p>' in html
    assert '<span class="visualmente-oculto">Duración: </span>2h 55m' in html
    assert '<h1 class="cartelera-titulo" id="cartelera-titulo">Películas en cartelera</h1>' in html


# --- Funciones de varios días: la fecha se ve y se anuncia en cada horario ------------------------------------


def _chip(html, funcion_id):
    return re.search(rf'<label class="chip-funcion">\s*<input [^>]*value="{funcion_id}"[^>]*>(.*?)</label>',
                     html, re.S).group(1)


def _texto_accesible(fragmento):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragmento)).strip()


def test_misma_hora_local_y_sala_en_dias_distintos_se_distinguen(cliente_frontend, llamar):
    funciones = [
        {"id": 21, "fecha_hora": "2026-11-10T21:00:00", "precio": 5500.0, "nombre_sala": "Sala 1",
         "nombre_local": "Paradiso Centro"},
        {"id": 22, "fecha_hora": "2026-11-11T21:00:00", "precio": 5500.0, "nombre_sala": "Sala 1",
         "nombre_local": "Paradiso Centro"},
    ]
    llamar.return_value = ({**PELICULA, "funciones": funciones}, None)
    html = _html(cliente_frontend, "/peliculas/1")

    # Fecha visible: un subgrupo por día dentro del local, y cada lista se nombra con su día.
    assert html.count(">Paradiso Centro</h3>") == 1
    assert '<p class="funciones-dia-titulo" id="funciones-dia-1-1">10/11</p>' in html
    assert '<p class="funciones-dia-titulo" id="funciones-dia-1-2">11/11</p>' in html
    assert 'aria-labelledby="funciones-dia-1-1"' in html and 'aria-labelledby="funciones-dia-1-2"' in html
    assert html.index('value="21"') < html.index(">11/11</p>") < html.index('value="22"')

    # Nombre accesible del radio (texto de su label): día, local, hora, sala y precio; distinto entre los dos.
    nombre_21 = _texto_accesible(_chip(html, 21))
    nombre_22 = _texto_accesible(_chip(html, 22))
    assert nombre_21 == "Función del 10/11, Paradiso Centro, a las 21:00, Sala 1 · $5.500"
    assert nombre_22 == "Función del 11/11, Paradiso Centro, a las 21:00, Sala 1 · $5.500"
    assert nombre_21 != nombre_22
