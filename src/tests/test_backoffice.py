"""Pruebas del layout y los componentes del backoffice (SCRUM-105)."""
import pytest

MACROS = '{% from "macros.html" import tabla, badge_estado, tarjeta_kpi, barra, cabecera_pagina %}'
COLUMNAS = [
    {"clave": "titulo", "titulo": "Título"},
    {"clave": "estado", "titulo": "Estado", "tipo": "estado"},
]
ACCIONES = {"editar": "editar", "baja": "baja"}


@pytest.fixture
def macro(app_frontend, renderizar):
    """Renderiza con las macros del backoffice y rutas de prueba para editar y baja."""
    app_frontend.add_url_rule("/editar/<int:id>", "editar", lambda id: "")
    app_frontend.add_url_rule("/baja/<int:id>", "baja", lambda id: "", methods=["POST"])
    return lambda plantilla, **contexto: renderizar(MACROS + plantilla, **contexto)


# --- layout ---
def test_backoffice_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/peliculas")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_backoffice_con_rol_cliente_devuelve_403(cliente_logueado):
    respuesta = cliente_logueado.get("/admin/dashboards")
    assert respuesta.status_code == 403
    assert "No tenés permiso para ver esta página" in respuesta.get_data(as_text=True)


def test_inicio_del_backoffice_redirige_a_dashboards(cliente_admin):
    respuesta = cliente_admin.get("/admin/")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/dashboards"


def test_sidebar_lista_las_secciones_y_marca_la_actual(cliente_admin):
    html = cliente_admin.get("/admin/peliculas").get_data(as_text=True)
    for texto in ("Dashboards", "Películas", "Funciones", "Locales y salas", "Servicios", "Validar ingreso"):
        assert texto in html
    assert 'href="/admin/peliculas" aria-current="page"' in html
    assert 'href="/admin/funciones" aria-current="page"' not in html
    assert 'type="checkbox" id="admin-menu-abierto"' in html
    assert 'class="marquesina"' not in html


def test_sidebar_muestra_el_nombre_del_admin(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="token-admin", rol="admin", nombre="Lucía")
    html = cliente_frontend.get("/admin/funciones").get_data(as_text=True)
    assert "Lucía" in html
    assert '<form method="post" action="/salir">' in html


def test_cerrar_sesion_limpia_la_sesion_y_redirige(cliente_admin):
    respuesta = cliente_admin.post("/salir")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    assert cliente_admin.get("/admin/dashboards").status_code == 302


# --- componentes ---
def test_tabla_con_filas_muestra_editar_y_baja_por_post(macro):
    filas = [{"id": 7, "titulo": "Cinema Paradiso", "estado": "activa", "activa": True}]
    html = macro("{{ tabla(columnas, filas, acciones) }}", columnas=COLUMNAS, filas=filas, acciones=ACCIONES)
    assert "Cinema Paradiso" in html
    assert 'href="/editar/7"' in html
    assert '<form method="post" action="/baja/7">' in html
    assert 'data-etiqueta="Título"' in html


def test_tabla_no_ofrece_baja_a_filas_inactivas(macro):
    filas = [{"id": 3, "titulo": "Nuovo", "estado": "inactiva", "activa": False}]
    html = macro("{{ tabla(columnas, filas, acciones) }}", columnas=COLUMNAS, filas=filas, acciones=ACCIONES)
    assert 'href="/editar/3"' in html
    assert "/baja/3" not in html


def test_tabla_vacia_muestra_mensaje(macro):
    html = macro("{{ tabla(columnas, [], vacio='No hay películas cargadas.') }}", columnas=COLUMNAS)
    assert "No hay películas cargadas." in html
    assert "<table" not in html


@pytest.mark.parametrize("estado", ["activa", "inactiva", "cancelada", "utilizada"])
def test_badge_estado_muestra_el_estado_en_texto(macro, estado):
    html = macro("{{ badge_estado(estado) }}", estado=estado)
    assert f'class="badge badge-{estado}">{estado.capitalize()}</span>' in html


def test_badge_estado_acepta_otra_leyenda(macro):
    html = macro("{{ badge_estado('activa', 'En cartelera') }}")
    assert 'class="badge badge-activa">En cartelera</span>' in html


def test_cabecera_pagina_con_y_sin_accion(macro):
    html = macro(
        "{{ cabecera_pagina('Películas', {'texto': 'Importar de TMDB', 'url': '/nueva'}, 'Cartelera del cine') }}"
    )
    assert "<h1>Películas</h1>" in html
    assert "Cartelera del cine" in html
    assert 'href="/nueva">Importar de TMDB</a>' in html
    assert "boton" not in macro("{{ cabecera_pagina('Funciones') }}")


def test_tarjeta_kpi_muestra_titulo_y_valor(macro):
    html = macro("{{ tarjeta_kpi('Entradas vendidas hoy', 312, '▲ 12% vs. ayer', 'positivo') }}")
    assert "Entradas vendidas hoy" in html
    assert '<p class="kpi-valor">312</p>' in html
    assert '<p class="kpi-detalle kpi-positivo">▲ 12% vs. ayer</p>' in html


@pytest.mark.parametrize("valor, maximo, ancho", [(30, 120, "25.0%"), (150, 100, "100%"), (5, 0, "0%")])
def test_barra_calcula_el_ancho_y_lo_limita(macro, valor, maximo, ancho):
    html = macro("{{ barra('Drama', valor, maximo) }}", valor=valor, maximo=maximo)
    assert f"width: {ancho}" in html
