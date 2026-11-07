"""Pruebas del perfil del cliente maquetado con datos de ejemplo (SCRUM-116)."""
import re
from datetime import datetime
from unittest.mock import patch

import pytest

from src.frontend.filtros import dia_semana
from src.frontend.routes.publico import _cancelable_hasta, _perfil_ejemplo, _pestana_compra


@pytest.fixture
def ahora_fijo():
    """Fecha actual fija: las compras de ejemplo de noviembre de 2026 quedan como próximas."""
    with patch("src.frontend.routes.publico.datetime") as reloj:
        reloj.now.return_value = datetime(2026, 11, 7, 12, 0)
        reloj.fromisoformat = datetime.fromisoformat
        yield reloj


def _compra(estado="confirmada", fecha_hora="2026-11-20T19:30:00", utilizada_en=None):
    return {"estado": estado, "utilizada_en": utilizada_en, "funcion": {"fecha_hora": fecha_hora}}


def _titulo_compra(titulo):
    return f">{titulo}</h2>"


def test_perfil_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/perfil")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/ingresar")


def test_perfil_con_sesion_muestra_cuenta_compras_y_vistas(cliente_logueado, ahora_fijo):
    respuesta = cliente_logueado.get("/perfil")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    for texto in ("Lucas Berardi", "lucas@email.com", "Cerrar sesión", "$23.000", "Pendiente de pago", "Confirmada",
                  "Ver QR", "Pagar ahora", "Se puede cancelar hasta las 17:30", "Se puede cancelar hasta las 19:00",
                  "Las butacas se liberan a las 19:42 si no pagás",
                  "Películas que viste", "Se suman cuando se valida tu QR al ingresar a la sala.", "Vista el 18/10",
                  "Paradiso Centro · Sala 1 · Vie 20/11 · 19:30", "Butacas D5, D6, D7 · Combo pochoclos grande × 1"):
        assert texto in html
    for titulo in ("La noche del telón", "Código medianoche", "Pequeños gigantes"):
        assert _titulo_compra(titulo) in html
    assert 'href="/perfil?estado=proximas" aria-current="page">Próximas</a>' in html
    assert 'href="/compras/1042/cancelar"' in html and 'href="/compras/1044/pago"' in html
    # A 14 días de la función 1043 (21/11) todavía se puede cancelar: la ruta calcula cancelable con la hora actual.
    assert 'href="/compras/1043/cancelar"' in html and "No se puede cancelar" not in html
    assert "<script" not in html and 'style="' not in html


@pytest.mark.parametrize("estado, visible, oculta", [
    ("historial", "Aventuras en el Plata", "La noche del telón"),
    ("canceladas", "Sombras del pasado", "Código medianoche"),
    ("cualquiera", "La noche del telón", "Sombras del pasado"),  # pestaña inválida: muestra las próximas
])
def test_perfil_filtra_compras_por_pestana(cliente_logueado, ahora_fijo, estado, visible, oculta):
    respuesta = cliente_logueado.get(f"/perfil?estado={estado}")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert _titulo_compra(visible) in html
    assert _titulo_compra(oculta) not in html


def test_pestana_compra_segun_estado_uso_y_fecha():
    ahora = datetime(2026, 11, 7, 12, 0)
    assert _pestana_compra(_compra(), ahora) == "proximas"
    assert _pestana_compra(_compra(estado="cancelada"), ahora) == "canceladas"
    assert _pestana_compra(_compra(utilizada_en="2026-11-07T11:00:00"), ahora) == "historial"
    assert _pestana_compra(_compra(fecha_hora="2026-11-01T20:00:00"), ahora) == "historial"


def test_dia_semana_en_espanol_y_tolera_valores_invalidos():
    assert dia_semana("2026-11-20T19:30:00") == "Vie 20/11"
    assert dia_semana("no es fecha") == "no es fecha"
    assert dia_semana(None) is None


# --- Bordes y casos adversariales (SCRUM-116) ---

MACROS_PERFIL = '{% from "macros.html" import tarjeta_compra, tarjeta_pelicula %}'
CANCELAR_HABILITADO = 'href="/compras/1042/cancelar"'
CANCELAR_DESHABILITADO = 'boton-deshabilitado" aria-disabled="true">Cancelar'


@pytest.fixture
def reloj():
    """Como ahora_fijo, pero cada prueba elige la hora actual con reloj.now.return_value."""
    with patch("src.frontend.routes.publico.datetime") as simulado:
        simulado.fromisoformat = datetime.fromisoformat
        yield simulado


def _pestana_marcada(html):
    """Cuántas pestañas del perfil quedaron marcadas (el header tiene su propio aria-current)."""
    return len(re.findall(r'href="/perfil\?estado=\w+" aria-current="page"', html))


def _compra_completa(**cambios):
    compra = {"id": 77, "estado": "confirmada", "total": 5000.0, "utilizada_en": None, "cancelable": True,
              "cancelable_hasta": "2026-11-20T17:30:00", "butacas": ["A1"], "servicios": [],
              "funcion": {"id": 1, "fecha_hora": "2026-11-20T19:30:00", "pelicula": "Prueba", "poster_url": None,
                          "sala": "Sala 1", "local": "Centro"}}
    compra.update(cambios)
    return compra


def _render_compra(renderizar, compra):
    return renderizar(MACROS_PERFIL + "{{ tarjeta_compra(compra, 2) }}", compra=compra)


# Sesión y rol
def test_perfil_con_token_vacio_redirige_al_login(cliente_frontend):
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token="", rol="cliente")
    respuesta = cliente_frontend.get("/perfil")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/ingresar")


def test_perfil_con_rol_admin_responde_200(cliente_admin, ahora_fijo):
    assert cliente_admin.get("/perfil").status_code == 200


def test_perfil_por_post_devuelve_405(cliente_logueado):
    assert cliente_logueado.post("/perfil").status_code == 405


def test_perfil_no_llama_al_backend(cliente_logueado, ahora_fijo):
    with patch("src.frontend.api_client.requests.request") as peticion:
        assert cliente_logueado.get("/perfil").status_code == 200
    peticion.assert_not_called()


# Query params raros en ?estado=
@pytest.mark.parametrize("consulta", [
    "?estado=", "?estado", "?estado=HISTORIAL", "?estado=%20historial", "?estado=historial%00",
    "?estado=cualquiera&estado=historial", "?estado=proximas&estado=canceladas", "?estado=" + "x" * 5000,  # valor muy largo
    "?otra=historial", "?estado=%3Cscript%3Ealert(1)%3C/script%3E", "?estado[]=historial",
])
def test_perfil_con_estado_desconocido_vacio_o_repetido_muestra_proximas(cliente_logueado, ahora_fijo, consulta):
    respuesta = cliente_logueado.get(f"/perfil{consulta}")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/perfil?estado=proximas" aria-current="page">Próximas</a>' in html
    assert _pestana_marcada(html) == 1
    assert _titulo_compra("La noche del telón") in html
    assert _titulo_compra("Sombras del pasado") not in html
    assert "<script>alert(1)" not in html


def test_perfil_con_estado_repetido_valido_usa_el_primero_y_no_rompe(cliente_logueado, ahora_fijo):
    # Flask toma el primer valor de un parámetro repetido: queda una sola pestaña marcada y no hay 500.
    respuesta = cliente_logueado.get("/perfil?estado=historial&estado=canceladas")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert _pestana_marcada(html) == 1
    assert 'href="/perfil?estado=historial" aria-current="page">Historial</a>' in html


@pytest.mark.parametrize("estado, titulos", [
    ("proximas", {"La noche del telón", "Código medianoche", "Pequeños gigantes"}),
    ("historial", {"Aventuras en el Plata"}),
    ("canceladas", {"Sombras del pasado"}),
])
def test_perfil_cada_pestana_muestra_solo_sus_compras(cliente_logueado, ahora_fijo, estado, titulos):
    html = cliente_logueado.get(f"/perfil?estado={estado}").get_data(as_text=True)
    todas = {compra["funcion"]["pelicula"] for compra in _perfil_ejemplo()["compras"]}
    for titulo in todas:
        assert (_titulo_compra(titulo) in html) == (titulo in titulos)


def test_perfil_pestana_vacia_muestra_mensaje(cliente_logueado, reloj):
    # Arrange: dentro de un año todas las funciones ya pasaron, no queda ninguna próxima.
    reloj.now.return_value = datetime(2027, 12, 1, 12, 0)
    html = cliente_logueado.get("/perfil?estado=proximas").get_data(as_text=True)
    assert "No tenés compras en esta sección." in html


def test_perfil_sin_peliculas_vistas_muestra_mensaje(cliente_logueado, ahora_fijo):
    datos = _perfil_ejemplo()
    datos["peliculas_vistas"] = []
    with patch("src.frontend.routes.publico._perfil_ejemplo", return_value=datos):
        html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert "Todavía no viste películas con nosotros." in html


def test_perfil_ejemplo_tiene_los_datos_que_usa_la_pantalla():
    datos = _perfil_ejemplo()
    assert {"id", "nombre", "email"} <= set(datos["usuario"])
    for compra in datos["compras"]:
        assert {"id", "estado", "total", "butacas", "servicios", "funcion", "cancelable"} <= set(compra)
        datetime.fromisoformat(compra["funcion"]["fecha_hora"])
        assert compra["estado"] in ("confirmada", "pendiente", "cancelada")
        assert not (compra["cancelable"] and compra["estado"] != "confirmada")
        if compra["estado"] == "pendiente":
            datetime.fromisoformat(compra["vence_en"])
    assert len({compra["id"] for compra in datos["compras"]}) == len(datos["compras"])


def test_perfil_ejemplo_devuelve_una_copia_nueva_en_cada_llamada():
    primero = _perfil_ejemplo()
    primero["compras"].clear()
    assert _perfil_ejemplo()["compras"]


# _pestana_compra en los límites
@pytest.mark.parametrize("fecha_hora, esperada", [
    ("2026-11-07T11:59:59", "historial"),  # empezó hace un segundo
    ("2026-11-07T12:00:00", "proximas"),   # empieza justo ahora
    ("2026-11-07T12:00:01", "proximas"),
])
def test_pestana_compra_en_el_limite_de_ahora(fecha_hora, esperada):
    assert _pestana_compra(_compra(fecha_hora=fecha_hora), datetime(2026, 11, 7, 12, 0)) == esperada


def test_pestana_compra_ignora_los_microsegundos_de_ahora():
    ahora = datetime(2026, 11, 7, 12, 0, 0, 999999)
    assert _pestana_compra(_compra(fecha_hora="2026-11-07T12:00:00"), ahora) == "proximas"


def test_pestana_compra_cancelada_y_usada_va_a_canceladas():
    compra = _compra(estado="cancelada", utilizada_en="2026-10-01T10:00:00", fecha_hora="2026-01-01T10:00:00")
    assert _pestana_compra(compra, datetime(2026, 11, 7, 12, 0)) == "canceladas"


def test_pestana_compra_pendiente_futura_es_proxima():
    assert _pestana_compra(_compra(estado="pendiente"), datetime(2026, 11, 7, 12, 0)) == "proximas"


# _cancelable_hasta
@pytest.mark.parametrize("fecha_hora, esperada", [
    ("2026-11-20T19:30:00", "2026-11-20T17:30:00"),
    ("2026-11-21T01:00:00", "2026-11-20T23:00:00"),  # cruza la medianoche
    ("2026-03-01T00:30:00", "2026-02-28T22:30:00"),  # cruza el mes
    ("2026-11-20T19:30", "2026-11-20T17:30:00"),     # sin segundos
])
def test_cancelable_hasta_resta_el_limite_de_horas(fecha_hora, esperada):
    assert _cancelable_hasta(fecha_hora, 2).isoformat() == esperada


def test_horas_limite_cancelacion_coincide_con_el_backend(app_frontend, app_backend):
    assert app_frontend.config["HORAS_LIMITE_CANCELACION"] == app_backend.config["HORAS_LIMITE_CANCELACION"]


# Botón Cancelar (macro tarjeta_compra)
def test_tarjeta_compra_confirmada_y_cancelable_ofrece_cancelar(renderizar):
    html = _render_compra(renderizar, _compra_completa())
    assert 'href="/compras/77/cancelar"' in html
    assert "Se puede cancelar hasta las 17:30" in html
    assert "aria-disabled" not in html


def test_tarjeta_compra_confirmada_no_cancelable_deshabilita_cancelar(renderizar):
    html = _render_compra(renderizar, _compra_completa(cancelable=False))
    assert CANCELAR_DESHABILITADO in html
    assert "/compras/77/cancelar" not in html
    assert "No se puede cancelar: faltan menos de 2 horas" in html


@pytest.mark.parametrize("cambios", [
    {"estado": "pendiente", "vence_en": "2026-11-07T19:42:00"},
    {"estado": "cancelada", "cancelada_en": "2026-10-20T12:10:00"},
    {"utilizada_en": "2026-11-20T19:10:00"},
    {"estado": "reembolsada"},
])
def test_tarjeta_compra_no_confirmada_o_usada_nunca_ofrece_cancelar(renderizar, cambios):
    # cancelable=True a propósito: aunque el dato venga mal, sin estado confirmada no hay link de cancelar.
    html = _render_compra(renderizar, _compra_completa(**cambios))
    assert "/compras/77/cancelar" not in html


def test_tarjeta_compra_con_estado_desconocido_muestra_el_estado_tal_cual(renderizar):
    html = _render_compra(renderizar, _compra_completa(estado="reembolsada"))
    assert 'badge-reembolsada">reembolsada</span>' in html


def test_tarjeta_compra_una_butaca_en_singular_y_sin_servicios(renderizar):
    html = _render_compra(renderizar, _compra_completa(butacas=["B4"]))
    assert "Butaca B4</p>" in html


def test_tarjeta_compra_usada_muestra_utilizada(renderizar):
    html = _render_compra(renderizar, _compra_completa(utilizada_en="2026-11-20T19:10:00"))
    assert 'badge-utilizada">Utilizada</span>' in html
    assert "Ingresaste el 20/11 · 19:10" in html


@pytest.mark.parametrize("cambios", [
    {"servicios": None}, {"butacas": []}, {"total": None}, {"vence_en": None, "estado": "pendiente"},
    {"cancelable_hasta": None},
])
def test_tarjeta_compra_con_datos_vacios_no_rompe(renderizar, cambios):
    compra = _compra_completa(**cambios)
    if compra["servicios"] is None:
        del compra["servicios"]
    assert "tarjeta-compra" in _render_compra(renderizar, compra)


def test_tarjeta_compra_escapa_el_titulo_de_la_pelicula(renderizar):
    compra = _compra_completa()
    compra["funcion"]["pelicula"] = "<script>alert(1)</script>"
    html = _render_compra(renderizar, compra)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("momento", [
    datetime(2026, 11, 20, 17, 30, 0),   # justo en el límite: el backend (ahora < límite) ya no deja cancelar
    datetime(2026, 11, 20, 17, 30, 1),
    datetime(2026, 11, 20, 18, 45, 0),   # a 45 minutos de la función
])
def test_perfil_deshabilita_cancelar_cuando_faltan_menos_de_2_horas(cliente_logueado, reloj, momento):
    reloj.now.return_value = momento
    html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert CANCELAR_HABILITADO not in html


def test_perfil_ofrece_cancelar_un_segundo_antes_del_limite(cliente_logueado, reloj):
    reloj.now.return_value = datetime(2026, 11, 20, 17, 29, 59)
    html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert CANCELAR_HABILITADO in html


@pytest.mark.parametrize("fecha_hora", ["", "20/11/2026 19:30"])
def test_perfil_con_fecha_de_funcion_vacia_o_mal_formada_no_rompe(cliente_logueado, ahora_fijo, fecha_hora):
    # Sin fecha válida la compra va al historial y no se puede cancelar.
    datos = _perfil_ejemplo()
    datos["compras"][0]["funcion"]["fecha_hora"] = fecha_hora
    with patch("src.frontend.routes.publico._perfil_ejemplo", return_value=datos):
        assert cliente_logueado.get("/perfil").status_code == 200


@pytest.mark.parametrize("fecha_hora", ["2027-01-01 al mediodía", "2027-13-01T10:00:00"])
def test_perfil_con_fecha_futura_mal_formada_no_rompe(cliente_logueado, ahora_fijo, fecha_hora):
    datos = _perfil_ejemplo()
    datos["compras"][0]["funcion"]["fecha_hora"] = fecha_hora
    with patch("src.frontend.routes.publico._perfil_ejemplo", return_value=datos):
        respuesta = cliente_logueado.get("/perfil")
    assert respuesta.status_code == 200


def test_perfil_con_fecha_de_funcion_nula_no_rompe(cliente_logueado, ahora_fijo):
    datos = _perfil_ejemplo()
    datos["compras"][0]["funcion"]["fecha_hora"] = None
    with patch("src.frontend.routes.publico._perfil_ejemplo", return_value=datos):
        respuesta = cliente_logueado.get("/perfil")
    assert respuesta.status_code == 200


# dia_semana
@pytest.mark.parametrize("valor, esperado", [
    ("2026-11-16T10:00:00", "Lun 16/11"), ("2026-11-17T10:00:00", "Mar 17/11"),
    ("2026-11-18T10:00:00", "Mié 18/11"), ("2026-11-19T10:00:00", "Jue 19/11"),
    ("2026-11-20T10:00:00", "Vie 20/11"), ("2026-11-21T10:00:00", "Sáb 21/11"),
    ("2026-11-22T10:00:00", "Dom 22/11"), ("2026-11-22", "Dom 22/11"),
    ("2026-02-29T10:00:00", "2026-02-29T10:00:00"),  # 2026 no es bisiesto: se devuelve tal cual
    ("2028-02-29T00:00:00", "Mar 29/02"),
    ("2026-11-20T23:59:59", "Vie 20/11"), ("2026-11-21T00:00:00", "Sáb 21/11"),
])
def test_dia_semana_devuelve_el_dia_en_espanol(valor, esperado):
    assert dia_semana(valor) == esperado


@pytest.mark.parametrize("valor", ["", "   ", "2026-13-01T10:00:00", "hoy", 20261120, 3.5, ["2026-11-20"], {}, b"2026-11-20"])
def test_dia_semana_con_valor_invalido_lo_devuelve_tal_cual(valor):
    assert dia_semana(valor) == valor


def test_dia_semana_esta_registrado_como_filtro_de_jinja(renderizar):
    assert renderizar("{{ fecha | dia_semana }}", fecha="2026-11-20T19:30:00") == "Vie 20/11"
    assert renderizar("{{ fecha | dia_semana }}", fecha=None) == "None"


# tarjeta_pelicula con los parámetros nuevos y su uso previo en la cartelera
PELICULA = {"id": 3, "titulo": "Aventuras", "duracion_min": 102, "clasificacion": "ATP", "genero": "Aventura",
            "poster_url": None}


def _render_pelicula(renderizar, llamada, pelicula=PELICULA):
    return renderizar(MACROS_PERFIL + "{{ " + llamada + " }}", pelicula=pelicula)


def test_tarjeta_pelicula_con_url_posicional_sigue_siendo_link_h2(renderizar):
    html = _render_pelicula(renderizar, "tarjeta_pelicula(pelicula, '/peliculas/3?local=Centro')")
    assert '<h2 class="tarjeta-pelicula-titulo"><a href="/peliculas/3?local=Centro">Aventuras</a></h2>' in html
    assert '<p class="tarjeta-pelicula-genero">Aventura</p>' in html


@pytest.mark.parametrize("llamada", ["tarjeta_pelicula(pelicula)", "tarjeta_pelicula(pelicula, '')",
                                     "tarjeta_pelicula(pelicula, none)"])
def test_tarjeta_pelicula_sin_url_no_genera_link(renderizar, llamada):
    html = _render_pelicula(renderizar, llamada)
    assert "<a " not in html
    assert '<h2 class="tarjeta-pelicula-titulo">Aventuras</h2>' in html


def test_tarjeta_pelicula_con_bajada_reemplaza_al_genero(renderizar):
    html = _render_pelicula(renderizar, "tarjeta_pelicula(pelicula, bajada='Vista el 18/10')")
    assert '<p class="tarjeta-pelicula-genero">Vista el 18/10</p>' in html
    assert "Aventura</p>" not in html


def test_tarjeta_pelicula_con_bajada_vacia_usa_el_genero(renderizar):
    html = _render_pelicula(renderizar, "tarjeta_pelicula(pelicula, bajada='')")
    assert '<p class="tarjeta-pelicula-genero">Aventura</p>' in html


@pytest.mark.parametrize("nivel", [2, 3, 4])
def test_tarjeta_pelicula_usa_el_nivel_de_titulo_pedido(renderizar, nivel):
    html = _render_pelicula(renderizar, f"tarjeta_pelicula(pelicula, nivel={nivel})")
    assert f'<h{nivel} class="tarjeta-pelicula-titulo">Aventuras</h{nivel}>' in html


def test_tarjeta_pelicula_sin_datos_no_rompe(renderizar):
    html = _render_pelicula(renderizar, "tarjeta_pelicula(pelicula, bajada='Vista el ')", pelicula={})
    assert "Película sin título" in html
    assert "Vista el" in html


def test_tarjeta_pelicula_escapa_url_y_bajada(renderizar):
    html = renderizar(MACROS_PERFIL + "{{ tarjeta_pelicula(pelicula, url, bajada=bajada) }}", pelicula=PELICULA,
                      url='"><script>x</script>', bajada="<b>hola</b>")
    assert "<script>" not in html and "<b>hola</b>" not in html


def test_perfil_peliculas_vistas_sin_link_con_h3_y_fecha(cliente_logueado, ahora_fijo):
    html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert '<h3 class="tarjeta-pelicula-titulo">El jardín de cristal</h3>' in html
    assert '<p class="tarjeta-pelicula-genero">Vista el 11/10</p>' in html


def test_perfil_pelicula_vista_sin_fecha_no_rompe(cliente_logueado, ahora_fijo):
    datos = _perfil_ejemplo()
    datos["peliculas_vistas"][0]["utilizada_en"] = None
    with patch("src.frontend.routes.publico._perfil_ejemplo", return_value=datos):
        respuesta = cliente_logueado.get("/perfil")
    assert respuesta.status_code == 200
