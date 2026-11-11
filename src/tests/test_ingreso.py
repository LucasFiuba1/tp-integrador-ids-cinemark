"""Pruebas de la pantalla de validar ingreso del backoffice (SCRUM-74): /admin/ingreso con el QR o el código pegado."""
from unittest.mock import patch

import pytest

from src.frontend.filtros import fecha_hora, hora
from src.frontend.validaciones import MAXIMO_CODIGO_QR

FUNCIONES_HOY = [
    {"id": 12, "pelicula": "Volver al futuro", "local": "Paradiso Centro", "sala": "Sala 1",
     "fecha_hora": "2026-11-10T20:30:00"},
    {"id": 13, "pelicula": "Código Medianoche", "local": "Paradiso Belgrano", "sala": "Sala 2",
     "fecha_hora": "2026-11-10T22:00:00"},
]
ENTRADA_VALIDA = {"valido": True, "compra_id": 88, "butacas": ["D5", "D6"], "pelicula": "Volver al futuro"}


def error_backend(status, codigo, mensaje):
    return {"status": status, "codigo": codigo, "mensaje": mensaje}


@pytest.fixture
def respuestas():
    """Lo que devuelve la API simulada: funciones de hoy, resultado de validar e historial. Cada prueba cambia lo que necesita."""
    return {"funciones": (FUNCIONES_HOY, None), "validar": (ENTRADA_VALIDA, None), "historial": ([], None)}


RUTAS_SIMULADAS = {"/api/admin/ingresos/validar": "validar", "/api/admin/ingresos": "historial"}


@pytest.fixture
def llamar(respuestas):
    def responder(metodo, ruta, json=None, params=None):
        return respuestas[RUTAS_SIMULADAS.get(ruta, "funciones")]
    with patch("src.frontend.routes.backoffice.llamar", side_effect=responder) as simulado:
        yield simulado


def llamadas_a(llamar, ruta):
    return [llamada for llamada in llamar.call_args_list if llamada.args[1] == ruta]


def llamadas_a_validar(llamar):
    return llamadas_a(llamar, "/api/admin/ingresos/validar")


def elegir_funcion(cliente, funcion_id=12):
    with cliente.session_transaction() as sesion:
        sesion["funcion_ingreso"] = funcion_id


# --- acceso ---
@pytest.mark.parametrize("metodo", ["get", "post"])
def test_ingreso_sin_sesion_redirige_al_login(cliente_frontend, metodo):
    respuesta = getattr(cliente_frontend, metodo)("/admin/ingreso")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_ingreso_como_cliente_devuelve_403(cliente_logueado):
    assert cliente_logueado.get("/admin/ingreso?token=abc").status_code == 403


def test_login_vuelve_a_la_url_del_qr_con_el_token(cliente_frontend):
    cliente_frontend.get("/admin/ingreso?token=abc.123")
    usuario = {"token": "token-admin", "rol": "admin", "nombre": "Admin"}
    with patch("src.frontend.routes.publico.llamar", return_value=(usuario, None)):
        respuesta = cliente_frontend.post("/ingresar", data={"email": "admin@paradiso.com", "password": "secreta123"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/ingreso?token=abc.123"
    with cliente_frontend.session_transaction() as sesion:
        assert "siguiente" not in sesion


def test_login_sin_pagina_pendiente_va_al_inicio_del_rol(cliente_frontend):
    usuario = {"token": "token-admin", "rol": "admin", "nombre": "Admin"}
    with patch("src.frontend.routes.publico.llamar", return_value=(usuario, None)):
        respuesta = cliente_frontend.post("/ingresar", data={"email": "admin@paradiso.com", "password": "secreta123"})
    assert respuesta.headers["Location"] == "/admin/"


def test_un_post_sin_sesion_no_queda_como_pagina_pendiente(cliente_frontend):
    cliente_frontend.post("/admin/ingreso", data={"token": "abc"})
    with cliente_frontend.session_transaction() as sesion:
        assert "siguiente" not in sesion


# --- GET: muestra el formulario sin validar ---
def test_get_con_token_lo_precarga_y_no_valida(cliente_admin, llamar):
    elegir_funcion(cliente_admin)
    respuesta = cliente_admin.get("/admin/ingreso?token=abc.123")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/ingreso" aria-current="page"' in html
    assert '<form method="post" action="/admin/ingreso" class="validar-formulario" novalidate>' in html
    assert 'name="token" value="abc.123"' in html
    assert '<option value="12" selected>' in html
    assert "20:30 · Volver al futuro · Paradiso Centro, Sala 1" in html
    assert "resultado-valido" not in html and "resultado-invalido" not in html
    assert llamadas_a_validar(llamar) == []


def test_get_pide_las_funciones_de_hoy(cliente_admin, llamar):
    cliente_admin.get("/admin/ingreso")
    [llamada] = llamadas_a(llamar, "/api/admin/funciones")
    params = llamada.kwargs["params"]
    assert llamada.args == ("GET", "/api/admin/funciones")
    assert params["desde"].endswith("T00:00:00") and params["hasta"].endswith("T23:59:59")
    assert params["desde"][:10] == params["hasta"][:10]


def test_get_pide_el_historial_de_la_funcion_elegida(cliente_admin, llamar, respuestas):
    elegir_funcion(cliente_admin)
    respuestas["historial"] = ([{"id": 1, "compra_id": 88, "funcion_id": 12, "hora": "2026-11-10T20:21:00",
                                 "pelicula": "Volver al futuro", "butacas": "D5, D6", "resultado": "valida"}], None)
    html = cliente_admin.get("/admin/ingreso").get_data(as_text=True)
    [llamada] = llamadas_a(llamar, "/api/admin/ingresos")
    assert llamada.kwargs["params"] == {"limite": 20, "funcion_id": 12}
    assert 'badge-valida">Válida</span>' in html and "D5, D6" in html


def test_get_sin_funcion_elegida_pide_el_historial_general(cliente_admin, llamar):
    cliente_admin.get("/admin/ingreso")
    [llamada] = llamadas_a(llamar, "/api/admin/ingresos")
    assert llamada.kwargs["params"] == {"limite": 20}


def test_historial_caido_muestra_la_pagina_igual(cliente_admin, llamar, respuestas):
    respuestas["historial"] = (None, error_backend(503, "SERVICIO_NO_DISPONIBLE", "El backend no responde."))
    respuesta = cliente_admin.get("/admin/ingreso")
    assert respuesta.status_code == 200
    assert "Todavía no hubo ingresos en esta jornada." in respuesta.get_data(as_text=True)


def test_get_con_token_sin_funcion_elegida_pide_elegirla(cliente_admin, llamar):
    html = cliente_admin.get("/admin/ingreso?token=abc.123").get_data(as_text=True)
    assert "Elegí la función que estás controlando antes de validar" in html
    assert 'name="token" value="abc.123"' in html


def test_get_sin_token_enfoca_el_campo(cliente_admin, llamar):
    html = cliente_admin.get("/admin/ingreso").get_data(as_text=True)
    assert 'name="token" value="" autocomplete="off" required autofocus' in html
    assert "Elegí la función que estás controlando antes de validar" not in html


def test_get_con_backend_caido_avisa_y_muestra_el_formulario(cliente_admin, llamar, respuestas):
    respuestas["funciones"] = (None, error_backend(503, "BACKEND_NO_DISPONIBLE", "No se pudo conectar con el servidor."))
    respuesta = cliente_admin.get("/admin/ingreso?token=abc")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "No se pudo conectar con el servidor." in html
    assert '<option value="" selected>' in html


# --- POST: valida en la API ---
def test_post_valido_muestra_acceso_permitido_y_las_butacas(cliente_admin, llamar):
    respuesta = cliente_admin.post("/admin/ingreso", data={"funcion_id": "12", "token": " abc.123 "})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "resultado-valido" in html and "Acceso permitido" in html
    for dato in ("D5, D6", "Volver al futuro", "#88"):
        assert f"<dd>{dato}</dd>" in html
    assert 'name="token" value=""' in html
    assert llamadas_a_validar(llamar)[0].kwargs["json"] == {"token_qr": "abc.123", "funcion_id": 12}


def test_post_guarda_la_funcion_en_la_sesion(cliente_admin, llamar):
    cliente_admin.post("/admin/ingreso", data={"funcion_id": "13", "token": "abc"})
    with cliente_admin.session_transaction() as sesion:
        assert sesion["funcion_ingreso"] == 13
    assert '<option value="13" selected>' in cliente_admin.get("/admin/ingreso").get_data(as_text=True)


@pytest.mark.parametrize("codigo, motivo", [
    ("QR_INVALIDO", "QR inválido"),
    ("CANCELADA", "Compra cancelada"),
    ("YA_UTILIZADA", "Entrada ya utilizada"),
    ("OTRA_FUNCION", "Es de otra función"),
    ("FUERA_DE_FECHA", "Fuera de fecha"),
])
def test_post_rechazado_muestra_el_motivo_en_rojo(cliente_admin, llamar, respuestas, codigo, motivo):
    respuestas["validar"] = (None, error_backend(409, codigo, "Detalle de la API."))
    respuesta = cliente_admin.post("/admin/ingreso", data={"funcion_id": "12", "token": "abc"})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "resultado-invalido" in html and "Acceso denegado" in html
    assert f"<strong>{motivo}</strong>. Detalle de la API." in html
    assert "Acceso permitido" not in html


def test_post_con_backend_caido_avisa_y_conserva_el_token(cliente_admin, llamar, respuestas):
    respuestas["validar"] = (None, error_backend(503, "BACKEND_NO_DISPONIBLE", "No se pudo conectar con el servidor."))
    html = cliente_admin.post("/admin/ingreso", data={"funcion_id": "12", "token": "abc"}).get_data(as_text=True)
    assert "No se pudo conectar con el servidor." in html
    assert 'name="token" value="abc"' in html
    assert "resultado-valido" not in html and "resultado-invalido" not in html


@pytest.mark.parametrize("datos, campo, mensaje", [
    ({"funcion_id": "", "token": "abc"}, "funcion_id", "Elegí la función que estás controlando."),
    ({"funcion_id": "²", "token": "abc"}, "funcion_id", "Elegí la función que estás controlando."),
    ({"funcion_id": "0", "token": "abc"}, "funcion_id", "Elegí la función que estás controlando."),
    ({"funcion_id": "12", "token": ""}, "token", "Escaneá el QR con la cámara o pegá el código de la entrada."),
    ({"funcion_id": "12", "token": "x" * (MAXIMO_CODIGO_QR + 1)}, "token", "El código es demasiado largo"),
    ({}, "funcion_id", "Elegí la función que estás controlando."),
])
def test_post_invalido_devuelve_400_sin_llamar_a_validar(cliente_admin, llamar, datos, campo, mensaje):
    respuesta = cliente_admin.post("/admin/ingreso", data=datos)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert f'aria-describedby="error-{campo}"' in html
    assert mensaje in html
    assert llamadas_a_validar(llamar) == []


def test_post_sin_funcion_conserva_el_token_pegado(cliente_admin, llamar):
    html = cliente_admin.post("/admin/ingreso", data={"funcion_id": "", "token": "abc.123"}).get_data(as_text=True)
    assert 'name="token" value="abc.123"' in html


# --- filtros y macros ---
@pytest.mark.parametrize("valor", ["no es fecha", None, ""])
def test_filtros_de_fecha_formatean_iso_y_toleran_valores_raros(valor):
    assert fecha_hora("2026-10-24T19:30:00") == "24/10 · 19:30"
    assert hora("2026-10-24T19:30:00") == "19:30"
    assert hora(valor) == valor


def test_tabla_formatea_horas_y_usa_la_leyenda_del_estado(renderizar):
    columnas = [{"clave": "hora", "titulo": "Hora", "tipo": "hora"},
                {"clave": "resultado", "titulo": "Resultado", "tipo": "estado", "textos": {"valida": "Válida"}}]
    filas = [{"hora": "2026-10-24T19:12:00", "resultado": "valida"}, {"hora": "x", "resultado": "cancelada"}]
    html = renderizar('{% from "macros.html" import tabla %}{{ tabla(c, f) }}', c=columnas, f=filas)
    assert "19:12" in html
    assert 'class="badge badge-valida">Válida</span>' in html
    assert 'class="badge badge-cancelada">Cancelada</span>' in html


# --- SCRUM-81: el lector del celular pega la URL entera del QR ---
@pytest.mark.parametrize("pegado", [
    "https://cine-paradiso-web.onrender.com/admin/ingreso?token=abc.def-123",
    "http://localhost:5001/admin/ingreso?token=abc.def-123",
    "  abc.def-123  ",
])
def test_post_con_la_url_del_qr_valida_solo_el_token(cliente_admin, llamar, pegado):
    cliente_admin.post("/admin/ingreso", data={"funcion_id": "12", "token": pegado})
    assert llamadas_a_validar(llamar)[0].kwargs["json"] == {"token_qr": "abc.def-123", "funcion_id": 12}


def test_post_con_una_url_sin_token_la_manda_tal_cual_y_el_backend_la_rechaza(cliente_admin, llamar):
    cliente_admin.post("/admin/ingreso", data={"funcion_id": "12", "token": "https://otro.sitio/promo"})
    assert llamadas_a_validar(llamar)[0].kwargs["json"]["token_qr"] == "https://otro.sitio/promo"
