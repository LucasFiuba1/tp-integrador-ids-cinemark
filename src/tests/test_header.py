"""Pruebas del header público (SCRUM-95, Figma Header/Desktop 23:221 y Header/Mobile 23:237): accesos según la
sesión, links sin romper, menú mobile sin JS, íconos locales y selectores de local y película."""
import re
from pathlib import Path

from flask import render_template_string

from src.frontend.header import ruta_disponible

CARPETA_ESTATICOS = Path(__file__).resolve().parents[1] / "frontend" / "static"
SELECTORES = (
    "{% from 'macros.html' import selectores_cartelera %}"
    "{{ selectores_cartelera('/', locales, peliculas, local, pelicula) }}"
)
LOCALES = [{"valor": 1, "texto": "Palermo"}, {"valor": 2, "texto": "Caballito"}]
PELICULAS = [{"valor": 7, "texto": "Cinema Paradiso"}]


def _header(html):
    return html[html.index('<header class="marquesina">'):html.index("</header>")]


def _iniciar_sesion(cliente, **datos):
    with cliente.session_transaction() as sesion:
        sesion.update(token="t", **datos)


def test_header_anonimo_ofrece_ingresar_y_no_salir(cliente_frontend, backend_ok):
    header = _header(cliente_frontend.get("/").get_data(as_text=True))
    assert '<a class="cabecera-usuario-boton" href="/ingresar">' in header
    assert '<span class="cabecera-usuario-texto">Ingresar</span>' in header
    assert 'action="/salir"' not in header
    assert "Backoffice" not in header
    assert "<details" not in header


def test_header_cliente_muestra_nombre_perfil_y_salir_por_post(cliente_frontend, backend_ok):
    _iniciar_sesion(cliente_frontend, rol="cliente", nombre="Ana")
    header = _header(cliente_frontend.get("/").get_data(as_text=True))
    assert '<details class="cabecera-usuario">' in header
    assert '<span class="visualmente-oculto">Cuenta de </span>Ana</span>' in header
    assert '<p class="cabecera-usuario-nombre">Ana</p>' in header
    assert '<form method="post" action="/salir">' in header
    assert "Mi perfil" in header
    assert "Backoffice" not in header
    assert 'href="/ingresar"' not in header


def test_header_admin_enlaza_al_backoffice(cliente_frontend, backend_ok):
    _iniciar_sesion(cliente_frontend, rol="admin", nombre="Marta")
    header = _header(cliente_frontend.get("/").get_data(as_text=True))
    assert '<a class="cabecera-enlace" href="/admin/">Backoffice</a>' in header
    assert '<p class="cabecera-usuario-nombre">Marta</p>' in header
    assert '<form method="post" action="/salir">' in header
    assert "Mi perfil" not in header


def test_header_admin_sin_nombre_usa_un_texto_por_defecto(cliente_admin, backend_ok):
    header = _header(cliente_admin.get("/").get_data(as_text=True))
    assert '<p class="cabecera-usuario-nombre">Administrador</p>' in header


def test_header_escapa_el_nombre_del_usuario(cliente_frontend, backend_ok):
    _iniciar_sesion(cliente_frontend, rol="cliente", nombre="<script>alert(1)</script>")
    html = cliente_frontend.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in _header(html)


def test_header_no_tiene_links_rotos(cliente_frontend, backend_ok):
    _iniciar_sesion(cliente_frontend, rol="admin", nombre="Marta")
    header = _header(cliente_frontend.get("/").get_data(as_text=True))
    enlaces = re.findall(r'href="([^"]*)"', header)
    assert enlaces and "#" not in enlaces and "" not in enlaces
    for enlace in enlaces:
        assert cliente_frontend.get(enlace).status_code in (200, 302)


def test_iconos_son_svg_locales_con_su_tamano(cliente_frontend, backend_ok):
    header = _header(cliente_frontend.get("/").get_data(as_text=True))
    assert "figma.com" not in header
    rutas = re.findall(r'(?:src|srcset)="/static/([^"]+)"', header)
    assert set(rutas) == {
        "img/header/menu-mobile.svg", "img/header/usuario-mobile.svg", "img/header/usuario-desktop.svg",
        "img/header/pin-mobile.svg", "img/header/pin-desktop.svg",
    }
    for ruta in rutas:
        svg = (CARPETA_ESTATICOS / ruta).read_text(encoding="utf-8")
        tamano = re.search(r'width="(\d+)"', svg).group(1)
        assert f'srcset="/static/{ruta}" width="{tamano}" height="{tamano}"' in header or \
            f'src="/static/{ruta}" width="{tamano}" height="{tamano}"' in header


def test_menu_enlaza_servicios_y_mis_compras(cliente_logueado, backend_ok):
    header = _header(cliente_logueado.get("/").get_data(as_text=True))
    assert '<a href="/servicios">Servicios</a>' in header
    assert '<a href="/mis-compras">Mis compras</a>' in header
    assert '<a href="/perfil">Mi perfil</a>' in header
    assert 'href="/" aria-current="page">Películas</a>' in header
    assert "menu-deshabilitado" not in header


def test_menu_marca_servicios_como_pagina_actual(cliente_frontend, backend_ok):
    header = _header(cliente_frontend.get("/servicios").get_data(as_text=True))
    assert '<a href="/servicios" aria-current="page">Servicios</a>' in header


def test_ruta_disponible_solo_con_endpoints_sin_parametros(app_frontend):
    with app_frontend.test_request_context():
        assert ruta_disponible("publico.inicio")
        assert ruta_disponible("publico.servicios")
        assert ruta_disponible("publico.mis_compras")
        assert ruta_disponible("backoffice.inicio")
        assert not ruta_disponible("publico.servicios_compra")  # pide compra_id
        assert not ruta_disponible("publico.no_existe")


def test_menu_mobile_se_abre_sin_js_y_con_etiqueta(cliente_frontend, backend_ok):
    html = cliente_frontend.get("/").get_data(as_text=True)
    header = _header(html)
    assert 'type="checkbox" id="cabecera-menu-abierto"' in header
    assert 'aria-controls="cabecera-menu"' in header and 'id="cabecera-menu"' in header
    assert '<label for="cabecera-menu-abierto" class="cabecera-boton">' in header
    assert '<span class="visualmente-oculto">Menú</span>' in header
    assert "<script" not in html


def test_navegacion_no_se_duplica(cliente_frontend, backend_ok):
    html = cliente_frontend.get("/").get_data(as_text=True)
    assert html.count('<header class="marquesina">') == 1
    assert html.count('aria-label="Principal"') == 1
    assert html.count('class="selectores"') == 1
    assert _header(html).count(">Películas</a>") == 1


def test_header_en_pantallas_publicas(cliente_frontend):
    assert '<header class="marquesina">' in cliente_frontend.get("/ingresar").get_data(as_text=True)


def test_backoffice_mantiene_su_sidebar_sin_header(cliente_admin):
    html = cliente_admin.get("/admin/dashboards").get_data(as_text=True)
    assert '<header class="marquesina">' not in html
    assert '<span class="marca">Cine Paradiso</span>' in html


def test_selectores_del_header_van_por_get_al_inicio(cliente_frontend, backend_ok):
    header = _header(cliente_frontend.get("/").get_data(as_text=True))
    assert '<form method="get" action="/" class="selectores"' in header
    assert '<label class="visualmente-oculto" for="cabecera-local_id">Local</label>' in header
    assert '<label class="visualmente-oculto" for="cabecera-pelicula_id">Película</label>' in header


def test_selectores_sin_catalogo_quedan_deshabilitados_con_descripcion(renderizar):
    html = renderizar(SELECTORES, locales=None, peliculas=[], local="", pelicula="")
    assert '<select id="selector-local_id" name="local_id" disabled aria-describedby="selector-local_id-ayuda">' in html
    assert '<option value="">Elegí local</option>' in html
    assert '<option value="">Elegí película</option>' in html
    assert 'id="selector-local_id-ayuda">Todavía no hay locales para elegir.</span>' in html
    assert 'id="selector-pelicula_id-ayuda">Todavía no hay películas para elegir.</span>' in html
    assert 'type="submit"' not in html


def test_selectores_con_opciones_mantienen_la_seleccion(renderizar):
    html = renderizar(SELECTORES, locales=LOCALES, peliculas=PELICULAS, local="2", pelicula="")
    assert '<option value="">Elegí local</option>' in html
    assert '<option value="2" selected>Caballito</option>' in html
    assert '<option value="1">Palermo</option>' in html
    assert '<option value="">Elegí película</option>' in html
    assert '<option value="7">Cinema Paradiso</option>' in html
    assert "disabled" not in html and "-ayuda" not in html
    assert '<button type="submit" class="selectores-enviar">Ver</button>' in html


def test_header_usa_el_catalogo_de_la_vista_y_los_query_params(app_frontend):
    plantilla = "{% include 'parciales/header.html' %}"
    with app_frontend.test_request_context("/?local_id=1&pelicula_id=7"):
        html = render_template_string(plantilla, header_locales=LOCALES, header_peliculas=PELICULAS)
    assert '<option value="1" selected>Palermo</option>' in html
    assert '<option value="7" selected>Cinema Paradiso</option>' in html
