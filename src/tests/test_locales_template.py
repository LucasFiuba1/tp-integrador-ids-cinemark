"""Pruebas de las pantallas del ABM de locales y salas del backoffice (SCRUM-55), con llamar simulado."""
from unittest.mock import patch

import pytest

from src.frontend.validaciones import validar_local, validar_sala

LLAMAR = "src.frontend.routes.backoffice.llamar"
CENTRO = {"id": 1, "nombre": "Paradiso Centro", "direccion": "Av. Corrientes 1234, CABA"}
PALERMO = {"id": 3, "nombre": "Paradiso Palermo", "direccion": "Av. Santa Fe 4321, CABA"}
SALA_VIP = {"id": 5, "local_id": 3, "local": "Paradiso Palermo", "nombre": "Sala VIP", "filas": 2, "columnas": 3,
            "capacidad": 6}
BUTACAS = [{"id": numero + (10 if fila == "B" else 0), "fila": fila, "numero": numero}
           for fila in "AB" for numero in (1, 2, 3)]
CAIDO = {"status": 503, "codigo": "BACKEND_NO_DISPONIBLE", "mensaje": "No se pudo conectar con el servidor."}


def _error(status, codigo, mensaje):
    return None, {"status": status, "codigo": codigo, "mensaje": mensaje}


def _html(respuesta):
    return respuesta.get_data(as_text=True)


# --- listado ---
def test_locales_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/locales")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_locales_muestra_cada_local_con_sus_salas(cliente_admin):
    with patch(LLAMAR, side_effect=[([CENTRO, PALERMO], None), ([SALA_VIP], None)]) as llamar:
        respuesta = cliente_admin.get("/admin/locales")
    html = _html(respuesta)
    assert respuesta.status_code == 200
    assert [llamada.args for llamada in llamar.call_args_list] == [("GET", "/api/admin/locales"),
                                                                    ("GET", "/api/admin/salas")]
    for dato in ("Paradiso Centro", "Paradiso Palermo", "Sala VIP", "6 butacas · 2 × 3"):
        assert dato in html
    assert 'href="/admin/salas/5"' in html
    assert 'action="/admin/salas/5/baja"' in html
    assert 'action="/admin/locales/1/baja"' in html
    assert 'href="/admin/locales/3/salas/nueva"' in html
    assert html.index("Paradiso Palermo") < html.index("Sala VIP")


def test_locales_con_backend_caido_muestra_el_error(cliente_admin):
    with patch(LLAMAR, return_value=(None, CAIDO)):
        respuesta = cliente_admin.get("/admin/locales")
    html = _html(respuesta)
    assert respuesta.status_code == 200
    assert "No se pudo conectar con el servidor." in html
    assert "Todavía no hay locales" in html


# --- locales: alta, edición y baja ---
def test_nuevo_local_valido_lo_crea_y_vuelve_al_listado(cliente_admin):
    with patch(LLAMAR, return_value=({"id": 4, **CENTRO}, None)) as llamar:
        respuesta = cliente_admin.post("/admin/locales/nuevo", data={"nombre": " Paradiso Centro ",
                                                                     "direccion": CENTRO["direccion"]})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/locales"
    llamar.assert_called_once_with("POST", "/api/admin/locales",
                                   json={"nombre": "Paradiso Centro", "direccion": CENTRO["direccion"]})


def test_nuevo_local_sin_datos_devuelve_400_sin_llamar_a_la_api(cliente_admin):
    with patch(LLAMAR) as llamar:
        respuesta = cliente_admin.post("/admin/locales/nuevo", data={"nombre": "", "direccion": ""})
    html = _html(respuesta)
    assert respuesta.status_code == 400
    assert "Ingresá el nombre del local." in html
    assert "Ingresá la dirección del local." in html
    llamar.assert_not_called()


def test_nuevo_local_duplicado_muestra_el_409_y_conserva_lo_escrito(cliente_admin):
    with patch(LLAMAR, return_value=_error(409, "LOCAL_DUPLICADO", "Ya existe un local con ese nombre o dirección.")):
        respuesta = cliente_admin.post("/admin/locales/nuevo", data={"nombre": "Paradiso Centro", "direccion": "X 1"})
    html = _html(respuesta)
    assert respuesta.status_code == 409
    assert "Ya existe un local con ese nombre o dirección." in html
    assert 'value="X 1"' in html


def test_editar_local_muestra_el_formulario_con_sus_datos(cliente_admin):
    with patch(LLAMAR, return_value=([CENTRO, PALERMO], None)):
        respuesta = cliente_admin.get("/admin/locales/1")
    html = _html(respuesta)
    assert respuesta.status_code == 200
    assert 'action="/admin/locales/1"' in html
    assert 'value="Av. Corrientes 1234, CABA"' in html


def test_editar_local_envia_put(cliente_admin):
    respuestas = [([CENTRO], None), ({"id": 1, "nombre": "Centro", "direccion": "Calle 2"}, None)]
    with patch(LLAMAR, side_effect=respuestas) as llamar:
        respuesta = cliente_admin.post("/admin/locales/1", data={"nombre": "Centro", "direccion": "Calle 2"})
    assert respuesta.status_code == 302
    assert llamar.call_args.args == ("PUT", "/api/admin/locales/1")
    assert llamar.call_args.kwargs == {"json": {"nombre": "Centro", "direccion": "Calle 2"}}


def test_editar_local_inexistente_vuelve_al_listado(cliente_admin):
    with patch(LLAMAR, return_value=([CENTRO], None)):
        respuesta = cliente_admin.get("/admin/locales/99", follow_redirects=False)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/locales"


def test_baja_de_local_con_salas_muestra_el_error_de_la_api(cliente_admin):
    error = _error(409, "LOCAL_CON_SALAS", "No se puede eliminar un local que tiene salas.")
    with patch(LLAMAR, side_effect=[error, ([], None)]) as llamar:
        respuesta = cliente_admin.post("/admin/locales/1/baja", follow_redirects=True)
    assert llamar.call_args_list[0].args == ("DELETE", "/api/admin/locales/1")
    assert "No se puede eliminar un local que tiene salas." in _html(respuesta)


# --- salas ---
def test_detalle_de_sala_muestra_la_grilla_en_solo_lectura(cliente_admin):
    with patch(LLAMAR, return_value=({**SALA_VIP, "butacas": BUTACAS}, None)) as llamar:
        respuesta = cliente_admin.get("/admin/salas/5")
    html = _html(respuesta)
    assert respuesta.status_code == 200
    llamar.assert_called_once_with("GET", "/api/admin/salas/5")
    assert "Paradiso Palermo" in html
    assert 'value="Sala VIP"' in html
    assert html.count('class="butaca-marca butaca-libre"') == 6
    assert 'name="butaca_ids"' not in html
    assert "butacas-leyenda" not in html
    assert 'action="/admin/salas/5/baja"' in html


def test_detalle_de_sala_inexistente_vuelve_al_listado(cliente_admin):
    with patch(LLAMAR, return_value=_error(404, "NO_ENCONTRADO", "La sala no existe.")):
        respuesta = cliente_admin.get("/admin/salas/99")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/locales"


def test_nueva_sala_valida_la_crea_y_va_a_su_detalle(cliente_admin):
    respuestas = [([PALERMO], None), ({"id": 6, "nombre": "Sala 3", "capacidad": 96}, None)]
    with patch(LLAMAR, side_effect=respuestas) as llamar:
        respuesta = cliente_admin.post("/admin/locales/3/salas/nueva",
                                       data={"nombre": "Sala 3", "filas": "8", "columnas": "12"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/salas/6"
    assert llamar.call_args.args == ("POST", "/api/admin/salas")
    assert llamar.call_args.kwargs == {"json": {"local_id": 3, "nombre": "Sala 3", "filas": 8, "columnas": 12}}


def test_nueva_sala_con_filas_invalidas_devuelve_400(cliente_admin):
    with patch(LLAMAR, return_value=([PALERMO], None)) as llamar:
        respuesta = cliente_admin.post("/admin/locales/3/salas/nueva",
                                       data={"nombre": "Sala 3", "filas": "27", "columnas": "abc"})
    html = _html(respuesta)
    assert respuesta.status_code == 400
    assert "entre 1 y 26" in html
    assert "entre 1 y 30" in html
    assert llamar.call_count == 1


def test_achicar_sala_con_funciones_muestra_el_409(cliente_admin):
    error = _error(409, "SALA_CON_FUNCIONES", "No se puede reducir una sala con funciones futuras.")
    with patch(LLAMAR, side_effect=[({**SALA_VIP, "butacas": BUTACAS}, None), error]) as llamar:
        respuesta = cliente_admin.post("/admin/salas/5", data={"nombre": "Sala VIP", "filas": "1", "columnas": "3"})
    html = _html(respuesta)
    assert respuesta.status_code == 409
    assert llamar.call_args.args == ("PUT", "/api/admin/salas/5")
    assert "No se puede reducir una sala con funciones futuras." in html
    assert 'value="1"' in html


def test_baja_de_sala_vuelve_al_listado(cliente_admin):
    with patch(LLAMAR, return_value=(None, None)) as llamar:
        respuesta = cliente_admin.post("/admin/salas/5/baja")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/locales"
    llamar.assert_called_once_with("DELETE", "/api/admin/salas/5")


# --- validaciones ---
@pytest.mark.parametrize("datos, campo", [
    ({"nombre": "", "direccion": "Calle 1"}, "nombre"),
    ({"nombre": "Centro", "direccion": "x" * 201}, "direccion"),
])
def test_validar_local_marca_el_campo_con_problema(datos, campo):
    assert list(validar_local(datos)) == [campo]


@pytest.mark.parametrize("filas, columnas, campos", [
    ("8", "12", []), ("26", "30", []), ("0", "12", ["filas"]), ("8", "31", ["columnas"]), ("-1", "1.5", ["filas", "columnas"]),
])
def test_validar_sala_acepta_de_1_a_26_filas_y_de_1_a_30_columnas(filas, columnas, campos):
    assert list(validar_sala({"nombre": "Sala 1", "filas": filas, "columnas": columnas})) == campos


def test_boton_baja_escapa_las_comillas_de_la_confirmacion(renderizar):
    html = renderizar('{% from "macros.html" import boton_baja %}{{ boton_baja("/x", "Quitar", pregunta) }}',
                      pregunta="¿Quitar la sala \"D'Artagnan\"?")
    assert 'onsubmit="return confirm(&#34;\\u00bfQuitar la sala \\&#34;D\\u0027Artagnan\\&#34;?&#34;)"' in html
