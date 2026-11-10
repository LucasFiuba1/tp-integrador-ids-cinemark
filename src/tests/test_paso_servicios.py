"""Pruebas del paso de servicios del flujo de compra (SCRUM-65): lista real, cantidades y total del backend."""
from unittest.mock import patch

import pytest

from src.frontend.validaciones import validar_cantidades_servicios, validar_sala

RUTA = "/compras/88/servicios"
SERVICIOS = [
    {"id": 4, "nombre": "Acceso VIP", "descripcion": "Butaca reclinable", "precio": 8000.0, "activo": True},
    {"id": 1, "nombre": "Combo pochoclos grande", "descripcion": None, "precio": 6500.0, "activo": True},
]
COMPRA = {"id": 88, "estado": "pendiente", "vence_en": "2099-11-10T20:10:00", "pelicula": "Volver al futuro",
          "poster_url": None, "local": "Paradiso Centro", "sala": "Sala 1", "funcion": "2099-11-10T20:30:00",
          "butacas": ["A1", "B1"], "subtotal_entradas": 10000.0, "total": 16500.0,
          "servicios": [{"servicio_id": 1, "nombre": "Combo pochoclos grande", "cantidad": 1,
                         "precio_unitario": 6500.0, "subtotal": 6500.0}]}
ERROR_SERVICIO = {"status": 400, "codigo": "DATOS_INVALIDOS",
                  "mensaje": "Uno o más servicios no existen o no están disponibles."}


def _api(compra=(COMPRA, None), servicios=(SERVICIOS, None), guardar=({"id": 88, "total": 23000.0}, None)):
    """Simula llamar(...): detalle de la compra, lista de servicios y el PUT de las cantidades."""
    def llamar(metodo, ruta, json=None, params=None):
        if metodo == "PUT":
            return guardar
        return servicios if ruta == "/api/servicios" else compra
    return patch("src.frontend.routes.publico.llamar", side_effect=llamar)


def _put(llamar):
    """Cuerpo del PUT enviado, o None si no se llamó."""
    for llamada in llamar.call_args_list:
        if llamada.args[0] == "PUT":
            assert llamada.args[1] == "/api/compras/88/servicios"
            return llamada.kwargs["json"]
    return None


def _flashes(cliente):
    with cliente.session_transaction() as sesion:
        return sesion.get("_flashes", [])


# --- GET ---
def test_muestra_los_servicios_activos_con_lo_ya_elegido_y_el_total_del_backend(cliente_logueado):
    with _api():
        respuesta = cliente_logueado.get(RUTA)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Acceso VIP" in html and "$8.000" in html and "Butaca reclinable" in html
    assert 'name="cantidad_4" value="0"' in html
    assert 'name="cantidad_1" value="1"' in html  # precargado desde compra["servicios"]
    assert html.count("servicio-elegido") == 1
    assert "$16.500" in html  # total que devolvió el backend, no uno sumado en el frontend
    assert 'max="20"' in html


def test_las_imagenes_salen_del_nombre_y_no_de_ids_fijos(cliente_logueado):
    with _api():
        html = cliente_logueado.get(RUTA).get_data(as_text=True)
    assert "<span>ACCESO</span>" in html and "<span>COMBO</span>" in html
    assert "servicio-imagen-4" in html and "servicio-imagen-1" in html


def test_los_botones_identifican_la_accion(cliente_logueado):
    with _api():
        html = cliente_logueado.get(RUTA).get_data(as_text=True)
    for valor in ("actualizar", "pago", "sin_servicios"):
        assert f'name="accion" value="{valor}"' in html
    assert html.count('form="form-servicios"') == 2
    # Enter usa el primer botón del formulario: tiene que ser "Actualizar total".
    assert html.index('value="actualizar"') < html.index('value="pago"')


def test_si_no_carga_la_lista_avisa_y_permite_seguir_sin_servicios(cliente_logueado):
    error = {"status": 503, "codigo": "SIN_CONEXION", "mensaje": "No pudimos conectar con el servidor."}
    with _api(servicios=(None, error)):
        respuesta = cliente_logueado.get(RUTA)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "No pudimos conectar con el servidor." in html
    assert "Podés seguir sin servicios." in html
    assert 'value="sin_servicios"' in html and 'value="actualizar"' not in html


def test_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get(RUTA)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].startswith("/ingresar")


# --- POST ---
def test_actualizar_guarda_solo_las_cantidades_positivas_y_vuelve_al_paso(cliente_logueado):
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA, data={"accion": "actualizar", "cantidad_4": "2", "cantidad_1": "0"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == RUTA
    assert _put(llamar) == [{"servicio_id": 4, "cantidad": 2}]
    assert ("exito", "Actualizamos el total de tu compra.") in _flashes(cliente_logueado)


def test_continuar_al_pago_guarda_y_sigue(cliente_logueado):
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": "1", "cantidad_1": "3"})
    assert respuesta.headers["Location"] == "/compras/88/pago"
    assert _put(llamar) == [{"servicio_id": 4, "cantidad": 1}, {"servicio_id": 1, "cantidad": 3}]


def test_continuar_sin_servicios_borra_los_elegidos_aunque_haya_campos_invalidos(cliente_logueado):
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA, data={"accion": "sin_servicios", "cantidad_4": "abc"})
    assert respuesta.headers["Location"] == "/compras/88/pago"
    assert _put(llamar) == []


@pytest.mark.parametrize("accion", [None, "", "otra"])
def test_accion_ausente_o_desconocida_solo_actualiza(cliente_logueado, accion):
    datos = {"cantidad_4": "1"} if accion is None else {"accion": accion, "cantidad_4": "1"}
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA, data=datos)
    assert respuesta.headers["Location"] == RUTA
    assert _put(llamar) == [{"servicio_id": 4, "cantidad": 1}]


def test_campos_vacios_cuentan_como_cero_y_los_de_otros_servicios_se_ignoran(cliente_logueado):
    with _api() as llamar:
        cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": " ", "cantidad_999": "5"})
    assert _put(llamar) == []


@pytest.mark.parametrize("valor", ["-1", "21", "abc", "1.5", "1e2", "²", "9" * 5000])
def test_cantidad_invalida_muestra_el_error_sin_llamar_al_backend(cliente_logueado, valor):
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": valor})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert "La cantidad tiene que ser un número entero entre 0 y 20." in html
    assert 'aria-describedby="error-cantidad_4"' in html
    assert _put(llamar) is None
    if len(valor) < 10:
        assert f'value="{valor}"' in html  # se conserva lo que escribió


def test_acepta_la_cantidad_maxima(cliente_logueado):
    with _api() as llamar:
        cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": "20"})
    assert _put(llamar) == [{"servicio_id": 4, "cantidad": 20}]


def test_error_400_del_backend_se_muestra_en_la_pagina(cliente_logueado):
    with _api(guardar=(None, ERROR_SERVICIO)):
        respuesta = cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": "1"})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert "Uno o más servicios no existen o no están disponibles." in html
    assert 'name="cantidad_4" value="1"' in html


@pytest.mark.parametrize("error", [
    {"status": 409, "codigo": "RESERVA_VENCIDA", "mensaje": "La reserva venció y se liberaron las butacas."},
    {"status": 409, "codigo": "COMPRA_NO_PENDIENTE", "mensaje": "La compra no está pendiente de pago."},
    {"status": 403, "codigo": "SIN_PERMISO", "mensaje": "No tenés permiso sobre esta compra."},
])
def test_compra_que_ya_no_se_puede_modificar_avisa_y_vuelve_al_inicio(cliente_logueado, error):
    with _api(guardar=(None, error)):
        respuesta = cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": "1"})
    assert respuesta.headers["Location"] == "/"
    assert ("error", error["mensaje"]) in _flashes(cliente_logueado)


def test_reserva_no_vigente_no_intenta_guardar(cliente_logueado):
    with _api(compra=(dict(COMPRA, vence_en="2020-01-01T10:00:00"), None)) as llamar:
        respuesta = cliente_logueado.post(RUTA, data={"accion": "pago", "cantidad_4": "1"})
    assert respuesta.headers["Location"] == "/"
    assert _put(llamar) is None


# --- validaciones ---
def test_validar_cantidades_acepta_de_0_a_20_y_marca_cada_campo():
    assert validar_cantidades_servicios({1: "0", 2: "20"}) == {}
    assert set(validar_cantidades_servicios({1: "21", 2: "3", 3: "x"})) == {1, 3}


def test_validar_sala_con_miles_de_digitos_no_rompe():
    errores = validar_sala({"nombre": "Sala 1", "filas": "9" * 5000, "columnas": "10"})
    assert errores == {"filas": "La cantidad de filas tiene que ser un número entero entre 1 y 26."}
