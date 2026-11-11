"""Pruebas del perfil del cliente (SCRUM-116 maqueta, SCRUM-50 integración con el backend).

El backend se simula parcheando llamar en la ruta: cada prueba puede cambiar las respuestas en perfil_api.
"""
import re
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from src.frontend.filtros import dia_semana
from src.frontend.routes.publico import RUTAS_PERFIL, _pestana_compra


def _perfil_api():
    """Respuestas de GET /api/auth/me, /api/me/compras y /api/me/peliculas-vistas (forma de docs/endpoints.md)."""
    return {
        "usuario": {"id": 7, "nombre": "Lucas Berardi", "email": "lucas@email.com", "rol": "cliente"},
        "compras": [
            {"id": 1042, "estado": "confirmada", "total": 23000.0, "utilizada_en": None, "vence_en": None,
             "funcion": {"id": 13, "pelicula_id": 5, "fecha_hora": "2026-11-20T19:30:00",
                         "pelicula": "La noche del telón",
                         "poster_url": None, "sala": "Sala 1", "local": "Paradiso Centro"},
             "butacas": ["D5", "D6", "D7"],
             "servicios": [{"nombre": "Combo pochoclos grande", "cantidad": 1, "precio_unitario": 6500.0}],
             "token_qr": "qr-1042", "cancelable": True, "cancelable_hasta": "2026-11-20T17:30:00"},
            {"id": 1043, "estado": "confirmada", "total": 19000.0, "utilizada_en": None, "vence_en": None,
             "funcion": {"id": 11, "pelicula_id": 6, "fecha_hora": "2026-11-21T21:00:00",
                         "pelicula": "Código medianoche",
                         "poster_url": None, "sala": "Sala VIP", "local": "Paradiso Palermo"},
             "butacas": ["B4"], "servicios": [{"nombre": "Acceso VIP", "cantidad": 1, "precio_unitario": 8000.0}],
             "token_qr": "qr-1043", "cancelable": True, "cancelable_hasta": "2026-11-21T19:00:00"},
            {"id": 1044, "estado": "pendiente", "total": 6000.0, "utilizada_en": None,
             "vence_en": "2026-11-07T19:42:00",
             "funcion": {"id": 12, "pelicula_id": 1, "fecha_hora": "2026-11-23T17:00:00",
                         "pelicula": "Pequeños gigantes",
                         "poster_url": None, "sala": "Sala 2", "local": "Paradiso Belgrano"},
             "butacas": ["F7"], "servicios": [], "token_qr": None, "cancelable": False,
             "cancelable_hasta": "2026-11-23T15:00:00"},
            {"id": 1031, "estado": "confirmada", "total": 16500.0, "utilizada_en": "2026-10-18T19:52:00",
             "vence_en": None,
             "funcion": {"id": 6, "pelicula_id": 3, "fecha_hora": "2026-10-18T20:00:00",
                         "pelicula": "Aventuras en el Plata",
                         "poster_url": None, "sala": "Sala 3", "local": "Paradiso Centro"},
             "butacas": ["E8", "E9"], "servicios": [], "token_qr": "qr-1031", "cancelable": False,
             "cancelable_hasta": "2026-10-18T18:00:00"},
            {"id": 1035, "estado": "cancelada", "total": 8500.0, "utilizada_en": None, "vence_en": None,
             "cancelada_en": "2026-10-20T12:10:00",
             "funcion": {"id": 9, "pelicula_id": 7, "fecha_hora": "2026-10-21T18:00:00",
                         "pelicula": "Sombras del pasado",
                         "poster_url": None, "sala": "Sala 1", "local": "Paradiso Belgrano"},
             "butacas": ["C7"], "servicios": [], "token_qr": None, "cancelable": False,
             "cancelable_hasta": "2026-10-21T16:00:00"},
        ],
        "peliculas_vistas": [
            {"pelicula_id": 3, "titulo": "Aventuras en el Plata", "poster_url": None, "duracion_min": 102,
             "clasificacion": "ATP", "genero": "Aventura", "utilizada_en": "2026-10-18T19:52:00"},
            {"pelicula_id": 4, "titulo": "El jardín de cristal", "poster_url": None, "duracion_min": 118,
             "clasificacion": "+13", "genero": "Drama", "utilizada_en": "2026-10-11T20:41:00"},
            {"pelicula_id": 1, "titulo": "Pequeños gigantes", "poster_url": None, "duracion_min": 95,
             "clasificacion": "ATP", "genero": "Animación", "utilizada_en": "2026-10-04T17:02:00"},
            {"pelicula_id": 2, "titulo": "Cuando cae la lluvia", "poster_url": None, "duracion_min": 124,
             "clasificacion": "+16", "genero": "Drama", "utilizada_en": "2026-09-27T21:55:00"},
        ],
    }


@pytest.fixture
def perfil_api():
    """Backend simulado: dict con las respuestas (editable en cada prueba) y el mock de llamar en la ruta."""
    datos = _perfil_api()
    claves = {ruta: clave for clave, ruta in RUTAS_PERFIL}

    def responder(metodo, ruta, json=None, params=None):
        return datos[claves[ruta]], None

    with patch("src.frontend.routes.publico.llamar", side_effect=responder) as llamar:
        yield {"datos": datos, "llamar": llamar}


@pytest.fixture
def ahora_fijo(perfil_api):
    """Fecha actual fija: las compras de noviembre de 2026 quedan como próximas."""
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
def reloj(perfil_api):
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


def test_perfil_pide_cuenta_compras_y_vistas_al_backend(cliente_logueado, ahora_fijo, perfil_api):
    assert cliente_logueado.get("/perfil").status_code == 200
    rutas = [llamada.args for llamada in perfil_api["llamar"].call_args_list]
    assert rutas == [("GET", "/api/auth/me"), ("GET", "/api/me/compras"), ("GET", "/api/me/peliculas-vistas")]


def test_perfil_con_backend_caido_avisa_sin_romper(cliente_logueado):
    # Sin parchear llamar: requests falla de verdad contra http://api.test y llamar devuelve BACKEND_NO_DISPONIBLE.
    with patch("src.frontend.api_client.requests.request", side_effect=requests.ConnectionError):
        respuesta = cliente_logueado.get("/perfil")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "No se pudo conectar con el servidor." in html
    assert "No pudimos cargar tus compras." in html and "No pudimos cargar las películas que viste." in html
    assert "No tenés compras en esta sección." not in html
    assert "<h1>Ana</h1>" in html  # el nombre sale de la sesión


def test_perfil_con_error_del_backend_muestra_el_mensaje(cliente_logueado):
    error = {"status": 500, "codigo": "ERROR", "mensaje": "El servidor respondió con un error."}
    with patch("src.frontend.routes.publico.llamar", return_value=(None, error)):
        html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert "El servidor respondió con un error." in html
    assert "No pudimos cargar tus compras." in html


def test_perfil_con_sesion_vencida_redirige_al_login(cliente_logueado):
    vencida = Mock(ok=False, status_code=401, content=b"{}")
    vencida.json.return_value = {"error": {"codigo": "TOKEN_INVALIDO", "mensaje": "El token es inválido o venció."}}
    with patch("src.frontend.api_client.requests.request", return_value=vencida):
        respuesta = cliente_logueado.get("/perfil")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/ingresar")


def test_perfil_sin_email_no_muestra_parrafo_vacio(cliente_logueado, ahora_fijo, perfil_api):
    del perfil_api["datos"]["usuario"]["email"]
    html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert "<p></p>" not in html and "<h1>Lucas Berardi</h1>" in html


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
    todas = {compra["funcion"]["pelicula"] for compra in _perfil_api()["compras"]}
    for titulo in todas:
        assert (_titulo_compra(titulo) in html) == (titulo in titulos)


def test_perfil_pestana_vacia_muestra_mensaje(cliente_logueado, reloj):
    # Arrange: dentro de un año todas las funciones ya pasaron, no queda ninguna próxima.
    reloj.now.return_value = datetime(2027, 12, 1, 12, 0)
    html = cliente_logueado.get("/perfil?estado=proximas").get_data(as_text=True)
    assert "No tenés compras en esta sección." in html


def test_perfil_sin_peliculas_vistas_muestra_mensaje(cliente_logueado, ahora_fijo, perfil_api):
    perfil_api["datos"]["peliculas_vistas"] = []
    html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert "Todavía no viste películas con nosotros." in html


def test_perfil_sin_compras_muestra_mensaje_en_cada_pestana(cliente_logueado, ahora_fijo, perfil_api):
    perfil_api["datos"]["compras"] = []
    for estado in ("proximas", "historial", "canceladas"):
        assert "No tenés compras en esta sección." in cliente_logueado.get(f"/perfil?estado={estado}").get_data(as_text=True)


@pytest.mark.parametrize("clave", ["compras", "peliculas_vistas", "usuario"])
def test_perfil_con_respuesta_nula_del_backend_no_rompe(cliente_logueado, ahora_fijo, perfil_api, clave):
    perfil_api["datos"][clave] = None
    assert cliente_logueado.get("/perfil").status_code == 200


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


def test_perfil_respeta_cancelable_del_backend(cliente_logueado, ahora_fijo, perfil_api):
    # El plazo lo decide el backend: si dice que no, el botón queda deshabilitado aunque falten días.
    perfil_api["datos"]["compras"][0]["cancelable"] = False
    html = cliente_logueado.get("/perfil").get_data(as_text=True)
    assert CANCELAR_HABILITADO not in html
    assert "No se puede cancelar: faltan menos de 2 horas" in html


@pytest.mark.parametrize("fecha_hora", ["", "20/11/2026 19:30"])
def test_perfil_con_fecha_de_funcion_vacia_o_mal_formada_no_rompe(cliente_logueado, ahora_fijo, fecha_hora, perfil_api):
    # Sin fecha válida la compra va al historial y no se puede cancelar.
    perfil_api["datos"]["compras"][0]["funcion"]["fecha_hora"] = fecha_hora
    assert cliente_logueado.get("/perfil").status_code == 200


@pytest.mark.parametrize("fecha_hora", ["2027-01-01 al mediodía", "2027-13-01T10:00:00"])
def test_perfil_con_fecha_futura_mal_formada_no_rompe(cliente_logueado, ahora_fijo, fecha_hora, perfil_api):
    perfil_api["datos"]["compras"][0]["funcion"]["fecha_hora"] = fecha_hora
    respuesta = cliente_logueado.get("/perfil")
    assert respuesta.status_code == 200


def test_perfil_con_fecha_de_funcion_nula_no_rompe(cliente_logueado, ahora_fijo, perfil_api):
    perfil_api["datos"]["compras"][0]["funcion"]["fecha_hora"] = None
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


def test_perfil_pelicula_vista_sin_fecha_no_rompe(cliente_logueado, ahora_fijo, perfil_api):
    perfil_api["datos"]["peliculas_vistas"][0]["utilizada_en"] = None
    respuesta = cliente_logueado.get("/perfil")
    assert respuesta.status_code == 200
