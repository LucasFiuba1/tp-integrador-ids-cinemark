"""Pruebas de la plantilla de programación de funciones del backoffice (SCRUM-119)."""
from datetime import datetime
from unittest.mock import patch

import pytest

from src.frontend.routes.backoffice import _funciones_ejemplo

RUTAS = [("get", "/admin/funciones"), ("post", "/admin/funciones"),
         ("get", "/admin/funciones/1"), ("post", "/admin/funciones/1/baja")]


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_funciones_sin_sesion_redirige_al_login(cliente_frontend, metodo, ruta):
    respuesta = getattr(cliente_frontend, metodo)(ruta)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_funciones_con_rol_cliente_devuelve_403(cliente_logueado, metodo, ruta):
    assert getattr(cliente_logueado, metodo)(ruta).status_code == 403


def test_funciones_con_admin_devuelve_200_con_sidebar_activo(cliente_admin):
    respuesta = cliente_admin.get("/admin/funciones")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/funciones" aria-current="page"' in html
    assert "Programación por local y sala" in html
    assert 'href="/admin/funciones#formulario-funcion">Nueva función</a>' in html
    assert "Esta sección está en construcción." not in html


def test_funciones_muestra_el_formulario_de_nueva_funcion(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert '<form method="post" action="/admin/funciones"' in html
    for nombre in ("pelicula_id", "local_id", "sala_id"):
        assert f'<select name="{nombre}"' in html
    for dato in ('type="date" name="fecha" value="2026-10-24"', 'type="time" name="hora" value="19:30"',
                 'type="number" name="precio" value="5500"', "Elegí una película", "Precio de la entrada",
                 ">Guardar función</button>", "El sistema valida que la sala esté libre en ese horario."):
        assert dato in html


def test_funciones_lista_las_funciones_con_fecha_precio_y_libres(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    for dato in ("La noche del telón", "Código Medianoche", "Pequeños gigantes", "Último tren a Lisboa",
                 "Paradiso Centro", "Paradiso Palermo", "Paradiso Belgrano", "Sala VIP",
                 "24/10 · 19:30", "24/10 · 22:15", "28/11 · 21:00", "29/11 · 15:00", "29/11 · 20:45",
                 "$5.500", "$9.500", "$6.000", "98 / 132", "120 / 132", "18 / 36", "84 / 96", "70 / 96"):
        assert dato in html


def test_funciones_ofrece_editar_y_quitar_por_post(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert 'href="/admin/funciones/3">Editar</a>' in html
    assert '<form method="post" action="/admin/funciones/3/baja">' in html
    assert html.count(">Quitar</button>") == 5


@pytest.mark.parametrize("metodo, ruta", RUTAS[1:])
def test_acciones_de_funciones_avisan_pendiente_y_vuelven_al_listado(cliente_admin, metodo, ruta):
    respuesta = getattr(cliente_admin, metodo)(ruta, data={"pelicula_id": "1", "precio": "5500"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/funciones"
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert "falta conectar el backend" in html


# --- Bordes y casos adversariales (SCRUM-119) ---
AVISO_PENDIENTE = "falta conectar el backend"
MACRO_TABLA = '{% from "macros.html" import tabla %}{{ tabla(columnas, filas) }}'
COLUMNAS_LIBRES = [{"clave": "sala", "titulo": "Sala"}, {"clave": "libres", "titulo": "Libres", "tipo": "libres"}]


def _celda_libres(html):
    """Texto de la primera celda Libres, sin espacios de sobra."""
    inicio = html.index('data-etiqueta="Libres">') + len('data-etiqueta="Libres">')
    return " ".join(html[inicio:html.index("</td>", inicio)].split())


def _sesion(cliente, **datos):
    with cliente.session_transaction() as sesion:
        sesion.update(datos)
    return cliente


# Permisos
@pytest.mark.parametrize("datos", [
    {"token": "t", "rol": "Admin"}, {"token": "t", "rol": "ADMIN"}, {"token": "t"}, {"token": "t", "rol": ""},
    {"token": "t", "rol": None}, {"token": "t", "rol": " admin"},
])
@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_funciones_con_rol_distinto_de_admin_devuelve_403(cliente_frontend, datos, metodo, ruta):
    assert getattr(_sesion(cliente_frontend, **datos), metodo)(ruta).status_code == 403


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_funciones_con_rol_admin_sin_token_redirige_al_login(cliente_frontend, metodo, ruta):
    respuesta = getattr(_sesion(cliente_frontend, rol="admin", token=""), metodo)(ruta)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_funciones_sin_sesion_por_post_no_muestra_el_aviso_pendiente(cliente_frontend):
    respuesta = cliente_frontend.post("/admin/funciones", data={"precio": "-1"}, follow_redirects=True)
    assert AVISO_PENDIENTE not in respuesta.get_data(as_text=True)


# Verbos y rutas
@pytest.mark.parametrize("metodo, ruta", [
    ("put", "/admin/funciones"), ("delete", "/admin/funciones"), ("patch", "/admin/funciones"),
    ("post", "/admin/funciones/1"), ("delete", "/admin/funciones/1"), ("get", "/admin/funciones/1/baja"),
])
def test_funciones_con_verbo_incorrecto_devuelve_405(cliente_admin, metodo, ruta):
    assert getattr(cliente_admin, metodo)(ruta).status_code == 405


@pytest.mark.parametrize("ruta", ["/admin/funciones/-1", "/admin/funciones/abc", "/admin/funciones/1.5",
                                  "/admin/funciones/abc/baja", "/admin/funciones//baja"])
def test_funciones_con_id_no_entero_devuelve_404(cliente_admin, ruta):
    metodo = cliente_admin.post if ruta.endswith("/baja") else cliente_admin.get
    assert metodo(ruta).status_code == 404


@pytest.mark.parametrize("metodo, ruta", [("get", "/admin/funciones/0"), ("post", "/admin/funciones/0/baja"),
                                          ("get", "/admin/funciones/999999999999"),
                                          ("post", "/admin/funciones/999999999999/baja")])
def test_acciones_con_id_cero_o_enorme_vuelven_al_listado(cliente_admin, metodo, ruta):
    respuesta = getattr(cliente_admin, metodo)(ruta)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/funciones"


# Formularios vacíos o inválidos: siempre PRG + aviso, nunca 500
FORMULARIOS_INVALIDOS = [
    {},
    {"pelicula_id": "", "local_id": "", "sala_id": "", "fecha": "", "hora": "", "precio": ""},
    {"pelicula_id": "1", "precio": "-5500"},
    {"pelicula_id": "1", "precio": "abc"},
    {"pelicula_id": "1", "precio": "1e309"},
    {"pelicula_id": "1", "precio": "NaN"},
    {"pelicula_id": "1", "fecha": "24/10/2026", "hora": "25:61"},
    {"pelicula_id": "1", "fecha": "2026-02-30", "hora": "19:30"},
    {"pelicula_id": "x' OR 1=1 --", "local_id": "<script>alert(1)</script>", "sala_id": "-1"},
    {"pelicula_id": ["1", "2"], "precio": ["1", "2"]},
    {"precio": "9" * 10000},
]


@pytest.mark.parametrize("formulario", FORMULARIOS_INVALIDOS)
@pytest.mark.parametrize("metodo, ruta", RUTAS[1:])
def test_acciones_con_formulario_vacio_o_invalido_redirigen_con_aviso(cliente_admin, formulario, metodo, ruta):
    respuesta = getattr(cliente_admin, metodo)(ruta, data=formulario, follow_redirects=True)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert respuesta.request.path == "/admin/funciones"
    assert AVISO_PENDIENTE in html
    assert "<script>alert(1)" not in html


def test_guardar_funcion_con_json_en_lugar_de_formulario_no_rompe(cliente_admin):
    respuesta = cliente_admin.post("/admin/funciones", json={"precio": -1})
    assert respuesta.status_code == 302


def test_acciones_de_funciones_no_llaman_al_backend(cliente_admin):
    with patch("src.frontend.routes.backoffice.llamar") as llamar, \
            patch("src.frontend.api_client.requests.request") as peticion:
        for metodo, ruta in RUTAS:
            getattr(cliente_admin, metodo)(ruta, data={"precio": "5500"})
    llamar.assert_not_called()
    peticion.assert_not_called()


def test_dos_post_seguidos_muestran_el_aviso_y_luego_se_consume(cliente_admin):
    cliente_admin.post("/admin/funciones", data={})
    cliente_admin.post("/admin/funciones", data={})
    primera = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    segunda = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert AVISO_PENDIENTE in primera
    assert AVISO_PENDIENTE not in segunda


def test_guardar_funcion_no_modifica_el_listado(cliente_admin):
    cliente_admin.post("/admin/funciones", data={"pelicula_id": "4", "precio": "1", "fecha": "2030-01-01"})
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert html.count(">Quitar</button>") == 5


# _funciones_ejemplo
def test_funciones_ejemplo_tiene_los_datos_que_usa_la_pantalla():
    datos = _funciones_ejemplo()
    assert {"peliculas", "locales", "salas", "formulario", "funciones"} <= set(datos)
    for funcion in datos["funciones"]:
        assert {"id", "pelicula", "local", "sala", "fecha_hora", "precio", "libres", "capacidad"} <= set(funcion)
        datetime.fromisoformat(funcion["fecha_hora"])
        assert 0 <= funcion["libres"] <= funcion["capacidad"]
        assert funcion["precio"] > 0
    assert len({funcion["id"] for funcion in datos["funciones"]}) == len(datos["funciones"])


def test_funciones_ejemplo_tiene_opciones_validas_para_los_selects():
    datos = _funciones_ejemplo()
    for clave in ("peliculas", "locales", "salas"):
        assert datos[clave]
        assert all({"valor", "texto"} <= set(opcion) for opcion in datos[clave])
    valores_locales = [opcion["valor"] for opcion in datos["locales"]]
    assert datos["formulario"]["local_id"] in valores_locales
    assert datos["formulario"]["sala_id"] in [opcion["valor"] for opcion in datos["salas"]]


def test_funciones_ejemplo_devuelve_una_copia_nueva_en_cada_llamada():
    datos = _funciones_ejemplo()
    datos["funciones"].clear()
    assert _funciones_ejemplo()["funciones"]


def test_funciones_sin_funciones_muestra_el_mensaje_vacio(cliente_admin):
    datos = _funciones_ejemplo()
    datos["funciones"] = []
    with patch("src.frontend.routes.backoffice._funciones_ejemplo", return_value=datos):
        html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert "Todavía no hay funciones programadas." in html
    assert '<form method="post" action="/admin/funciones"' in html


def test_funciones_con_formulario_sin_valores_no_rompe(cliente_admin):
    datos = _funciones_ejemplo()
    datos["formulario"] = {}
    with patch("src.frontend.routes.backoffice._funciones_ejemplo", return_value=datos):
        assert cliente_admin.get("/admin/funciones").status_code == 200


def test_funciones_escapa_los_textos_de_las_funciones(cliente_admin):
    datos = _funciones_ejemplo()
    datos["funciones"][0]["pelicula"] = "<script>alert(1)</script>"
    with patch("src.frontend.routes.backoffice._funciones_ejemplo", return_value=datos):
        html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)" in html


def test_funciones_marca_la_sala_y_el_local_del_formulario(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert html.count(" selected>") == 3  # película vacía, local 1 y sala 1


# Macro tabla con tipo "libres"
@pytest.mark.parametrize("fila, esperado", [
    ({"id": 1, "sala": "S1", "libres": 98, "capacidad": 132}, "98 / 132"),
    ({"id": 1, "sala": "S1", "libres": 0, "capacidad": 132}, "0 / 132"),
    ({"id": 1, "sala": "S1", "libres": 0, "capacidad": 0}, "0 / 0"),
    ({"id": 1, "sala": "S1", "libres": 132, "capacidad": 132}, "132 / 132"),
    ({"id": 1, "sala": "S1", "capacidad": 132}, "/ 132"),  # falta libres
    ({"id": 1, "sala": "S1", "libres": 98}, "98 /"),       # falta capacidad
    ({"id": 1, "sala": "S1"}, "/"),                        # faltan ambas
])
def test_tabla_libres_no_rompe_si_faltan_datos(renderizar, fila, esperado):
    html = renderizar(MACRO_TABLA, columnas=COLUMNAS_LIBRES, filas=[fila])
    assert _celda_libres(html) == esperado


@pytest.mark.xfail(
    reason="BUG: la macro tabla con tipo 'libres' imprime 'None' cuando libres o capacidad llegan en null.",
    raises=AssertionError, strict=True)
@pytest.mark.parametrize("fila", [{"id": 1, "libres": None, "capacidad": 132},
                                  {"id": 1, "libres": 98, "capacidad": None}])
def test_tabla_libres_con_valores_nulos_no_muestra_none(renderizar, fila):
    html = renderizar(MACRO_TABLA, columnas=COLUMNAS_LIBRES, filas=[fila])
    assert "None" not in _celda_libres(html)


def test_tabla_libres_escapa_los_valores(renderizar):
    fila = {"id": 1, "sala": "S", "libres": "<b>1</b>", "capacidad": "<i>2</i>"}
    html = renderizar(MACRO_TABLA, columnas=COLUMNAS_LIBRES, filas=[fila])
    assert "<b>" not in html and "<i>" not in html


def test_tabla_libres_con_varias_filas_usa_la_capacidad_de_cada_fila(renderizar):
    filas = [{"id": 1, "libres": 1, "capacidad": 10}, {"id": 2, "libres": 2, "capacidad": 20}]
    html = " ".join(renderizar(MACRO_TABLA, columnas=COLUMNAS_LIBRES, filas=filas).split())
    assert "1 / 10" in html and "2 / 20" in html
    assert "1 / 20" not in html and "2 / 10" not in html


@pytest.mark.parametrize("tipo, valor, esperado", [
    (None, "Sala 1", "Sala 1"), ("precio", 6500, "$6.500"), ("hora", "2026-10-24T19:30:00", "19:30"),
    ("fecha_hora", "2026-10-24T19:30:00", "24/10 · 19:30"), ("duracion", 125, "2h 5m"),
])
def test_tabla_sigue_renderizando_los_tipos_previos(renderizar, tipo, valor, esperado):
    columnas = [{"clave": "dato", "titulo": "Dato", "tipo": tipo}]
    html = renderizar(MACRO_TABLA, columnas=columnas, filas=[{"id": 1, "dato": valor, "capacidad": 999}])
    assert esperado in html
    assert " / " not in html.replace("</", "")


@pytest.mark.parametrize("ruta, texto", [
    ("/admin/servicios", '<table class="tabla">'), ("/admin/peliculas", "Películas"), ("/admin/locales", "Locales"),
])
def test_otras_pantallas_del_backoffice_siguen_respondiendo(cliente_admin, ruta, texto):
    with patch("src.frontend.routes.backoffice.llamar", return_value=([], None)):
        respuesta = cliente_admin.get(ruta)
    assert respuesta.status_code == 200
    assert texto in respuesta.get_data(as_text=True)
