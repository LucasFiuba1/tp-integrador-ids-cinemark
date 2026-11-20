"""Pruebas del pago y la compra confirmada con la compra real (SCRUM-68, sobre los templates de SCRUM-114) y la validación del pago."""
from datetime import date
from unittest.mock import patch

import pytest

from src.frontend.filtros import precio
from src.frontend.routes import publico
from src.frontend.validaciones import validar_pago

PAGO_VALIDO = {"titular": "Lucas Berardi", "numero": "4242 4242 4242 4242", "vencimiento": "12/28",
               "codigo_seguridad": "123", "acepto": "si"}
HOY = date(2026, 10, 31)


# --- pantallas con la compra real (SCRUM-68) ---
RUTA_PAGO = "/compras/1042/pago"
RUTA_CONFIRMADA = "/compras/1042/confirmada"
COMPRA = {
    "id": 1042, "estado": "pendiente", "vence_en": "2099-10-24T19:05:00", "pelicula": "La noche del telón",
    "poster_url": None, "local": "Paradiso Centro", "sala": "Sala 1", "funcion": "2099-10-24T19:30:00",
    "butacas": ["D5", "D6", "D7"], "subtotal_entradas": 16500,
    "servicios": [{"servicio_id": 1, "nombre": "Combo pochoclos grande", "cantidad": 1, "precio_unitario": 6500,
                   "subtotal": 6500}],
    "total": 23000, "email": "lucas@email.com", "qr_png_base64": None, "cancelable": False,
}
COMPRA_CONFIRMADA = dict(COMPRA, estado="confirmada", vence_en=None, qr_png_base64="iVBORw0KGgoQRDEPRUEBA",
                         cancelable=True)
CONFIRMADO = ({"id": 1042, "estado": "confirmada", "total": 23000.0, "qr_png_base64": "iVBORw0KGgoQRDEPRUEBA",
               "email_enviado": True}, None)
YA_CONFIRMADA = {"status": 409, "codigo": "COMPRA_NO_PENDIENTE", "mensaje": "La compra no está pendiente de pago."}
RESERVA_VENCIDA = {"status": 409, "codigo": "RESERVA_VENCIDA", "mensaje": "La reserva venció y se liberaron las butacas."}
SIN_CONEXION = {"status": 503, "codigo": "BACKEND_NO_DISPONIBLE", "mensaje": "No se pudo conectar con el servidor."}


def _api(compras=(COMPRA,), confirmar=CONFIRMADO):
    """Simula llamar(...): cada GET /api/compras/<id> devuelve la siguiente de `compras` (la última se repite; un
    elemento puede ser una tupla (datos, error)) y el POST .../confirmar devuelve `confirmar`."""
    pendientes = list(compras)

    def llamar(metodo, ruta, json=None, params=None):
        if metodo == "POST":
            return confirmar
        detalle = pendientes.pop(0) if len(pendientes) > 1 else pendientes[0]
        return detalle if isinstance(detalle, tuple) else (detalle, None)

    return patch("src.frontend.routes.publico.llamar", side_effect=llamar)


def _confirmaciones(llamar):
    return [llamada for llamada in llamar.call_args_list if llamada.args[0] == "POST"]


def _flashes(cliente):
    with cliente.session_transaction() as sesion:
        return sesion.get("_flashes", [])


def test_pago_muestra_pasos_formulario_y_resumen_de_la_compra_real(cliente_logueado):
    with _api():
        respuesta = cliente_logueado.get(RUTA_PAGO)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert '<li class="paso paso-hecho">' in html
    assert '<li class="paso paso-actual" aria-current="step">' in html
    assert 'Pago simulado: no se realiza ningún cobro real.' in html
    assert '<form id="formulario-pago" method="post" action="/compras/1042/pago" novalidate>' in html
    for nombre in ("titular", "numero", "vencimiento", "codigo_seguridad", "acepto"):
        assert f'name="{nombre}"' in html
    assert 'form="formulario-pago">Confirmar y pagar</button>' in html
    for dato in ("La noche del telón", "3 entradas", "Combo pochoclos grande × 1", "$16.500", "$23.000", "19:05"):
        assert dato in html


def test_pago_deshabilita_el_boton_al_enviar_sin_hacer_peticiones(cliente_logueado):
    with _api():
        html = cliente_logueado.get(RUTA_PAGO).get_data(as_text=True)
    assert 'addEventListener("submit"' in html and "boton.disabled = true" in html
    for prohibido in ("fetch", "XMLHttpRequest", "axios", "Promise", "async "):
        assert prohibido not in html


def test_pago_valido_confirma_en_el_backend_y_redirige_a_compra_confirmada(cliente_logueado):
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == RUTA_CONFIRMADA
    assert [c.args for c in _confirmaciones(llamar)] == [("POST", "/api/compras/1042/confirmar")]
    # la tarjeta es solo del formulario: no viaja al backend
    assert _confirmaciones(llamar)[0].kwargs == {}


def test_pago_valido_con_email_fallido_lo_recuerda_para_avisarlo(cliente_logueado):
    fallo = (dict(CONFIRMADO[0], email_enviado=False), None)
    with _api(confirmar=fallo):
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.headers["Location"] == RUTA_CONFIRMADA
    with cliente_logueado.session_transaction() as sesion:
        assert sesion["email_fallido"] == 1042


def test_pago_con_errores_devuelve_400_sin_confirmar_ni_repetir_los_datos_de_la_tarjeta(cliente_logueado):
    with _api() as llamar:
        respuesta = cliente_logueado.post(RUTA_PAGO, data=dict(PAGO_VALIDO, vencimiento="13/28", acepto=""))
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert 'id="error-vencimiento">Ingresá el vencimiento como MM/AA' in html
    assert 'id="error-acepto">Tenés que aceptar' in html
    assert 'value="Lucas Berardi"' in html
    assert 'value="4242' not in html
    assert 'value="123"' not in html
    assert _confirmaciones(llamar) == []


def test_doble_clic_en_pagar_lleva_a_la_compra_ya_confirmada_sin_error(cliente_logueado):
    # La petición vio la compra pendiente, pero otra ya la confirmó: el backend rechaza la confirmación (409).
    with _api(compras=(COMPRA, COMPRA_CONFIRMADA), confirmar=(None, YA_CONFIRMADA)):
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == RUTA_CONFIRMADA
    assert _flashes(cliente_logueado) == []


def test_pagar_una_compra_que_ya_estaba_confirmada_no_vuelve_a_confirmarla(cliente_logueado):
    with _api(compras=(COMPRA_CONFIRMADA,)) as llamar:
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.headers["Location"] == RUTA_CONFIRMADA
    assert _confirmaciones(llamar) == []


def test_pago_con_409_de_una_compra_que_no_quedo_confirmada_avisa_y_vuelve_al_inicio(cliente_logueado):
    cancelada = dict(COMPRA, estado="cancelada", vence_en=None)
    with _api(compras=(COMPRA, cancelada), confirmar=(None, YA_CONFIRMADA)):
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_logueado) == [("error", YA_CONFIRMADA["mensaje"])]


def test_pago_con_reserva_vencida_en_el_backend_avisa_y_vuelve_al_inicio(cliente_logueado):
    with _api(confirmar=(None, RESERVA_VENCIDA)):
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_logueado) == [("error", RESERVA_VENCIDA["mensaje"])]


def test_pago_con_backend_caido_al_confirmar_vuelve_al_formulario_para_reintentar(cliente_logueado):
    with _api(confirmar=(None, SIN_CONEXION)):
        respuesta = cliente_logueado.post(RUTA_PAGO, data=PAGO_VALIDO)
    assert respuesta.headers["Location"] == RUTA_PAGO
    assert _flashes(cliente_logueado) == [("error", SIN_CONEXION["mensaje"])]


@pytest.mark.parametrize("compra", [
    dict(COMPRA, vence_en="2000-01-01T00:00:00"),  # plazo vencido que el backend todavía no marcó
    dict(COMPRA, estado="vencida", vence_en=None),
    dict(COMPRA, estado="cancelada", vence_en=None),
])
def test_pago_de_una_reserva_que_ya_no_esta_activa_avisa_y_vuelve_al_inicio(cliente_logueado, compra):
    with _api(compras=(compra,)):
        respuesta = cliente_logueado.get(RUTA_PAGO)
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_logueado) == [("error", "Esta reserva ya no está activa. Elegí tus butacas de nuevo.")]


def test_pago_de_una_compra_inexistente_o_ajena_avisa_y_vuelve_al_inicio(cliente_logueado):
    ajena = (None, {"status": 403, "codigo": "SIN_PERMISO", "mensaje": "No tenés permiso sobre esta compra."})
    with _api(compras=(ajena,)):
        respuesta = cliente_logueado.get(RUTA_PAGO)
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_logueado) == [("error", "No tenés permiso sobre esta compra.")]


def test_pago_de_una_compra_ya_confirmada_lleva_a_la_confirmacion(cliente_logueado):
    with _api(compras=(COMPRA_CONFIRMADA,)):
        respuesta = cliente_logueado.get(RUTA_PAGO)
    assert respuesta.headers["Location"] == RUTA_CONFIRMADA


def test_compra_confirmada_muestra_qr_y_datos_de_la_compra_real(cliente_logueado):
    with _api(compras=(COMPRA_CONFIRMADA,)):
        respuesta = cliente_logueado.get(RUTA_CONFIRMADA)
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "¡Compra confirmada!" in html
    assert 'src="data:image/png;base64,iVBORw0KGgoQRDEPRUEBA"' in html
    assert 'alt="Código QR de ingreso de la compra #1042"' in html
    for dato in ("Paradiso Centro", "24/10 · 19:30", "D5, D6, D7", "Combo pochoclos grande × 1"):
        assert f"<dd>{dato}</dd>" in html
    assert "<strong>$23.000</strong>" in html
    assert "Enviamos la factura y tu QR de ingreso a lucas@email.com" in html
    assert "No pudimos enviar el email" not in html
    assert 'href="/">Volver a cartelera</a>' in html
    assert 'href="/perfil">Ver mis compras</a>' in html


def test_compra_confirmada_avisa_si_el_email_no_pudo_enviarse_y_sigue_mostrando_el_qr(cliente_logueado):
    with cliente_logueado.session_transaction() as sesion:
        sesion["email_fallido"] = 1042
    with _api(compras=(COMPRA_CONFIRMADA,)):
        html = cliente_logueado.get(RUTA_CONFIRMADA).get_data(as_text=True)
    assert "No pudimos enviar el email a lucas@email.com" in html
    assert "Enviamos la factura" not in html
    assert 'src="data:image/png;base64,iVBORw0KGgoQRDEPRUEBA"' in html


def test_compra_confirmada_ignora_el_email_fallido_de_otra_compra(cliente_logueado):
    with cliente_logueado.session_transaction() as sesion:
        sesion["email_fallido"] = 999
    with _api(compras=(COMPRA_CONFIRMADA,)):
        html = cliente_logueado.get(RUTA_CONFIRMADA).get_data(as_text=True)
    assert "Enviamos la factura y tu QR de ingreso" in html


def test_compra_confirmada_de_una_compra_pendiente_lleva_al_pago(cliente_logueado):
    with _api(compras=(COMPRA,)):
        respuesta = cliente_logueado.get(RUTA_CONFIRMADA)
    assert respuesta.headers["Location"] == RUTA_PAGO
    assert _flashes(cliente_logueado) == [("error", "Completá el pago para confirmar tu compra.")]


def test_compra_confirmada_de_una_compra_cancelada_vuelve_al_inicio(cliente_logueado):
    with _api(compras=(dict(COMPRA, estado="cancelada", vence_en=None),)):
        respuesta = cliente_logueado.get(RUTA_CONFIRMADA)
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_logueado) == [("error", "Esta compra no está confirmada.")]


def test_compra_confirmada_con_error_del_backend_avisa_y_vuelve_al_inicio(cliente_logueado):
    with _api(compras=((None, SIN_CONEXION),)):
        respuesta = cliente_logueado.get(RUTA_CONFIRMADA)
    assert respuesta.headers["Location"] == "/"
    assert _flashes(cliente_logueado) == [("error", SIN_CONEXION["mensaje"])]


@pytest.mark.parametrize("metodo, ruta", [("get", RUTA_PAGO), ("post", RUTA_PAGO), ("get", RUTA_CONFIRMADA)])
def test_pago_y_confirmada_sin_sesion_redirigen_al_login(cliente_frontend, metodo, ruta):
    respuesta = getattr(cliente_frontend, metodo)(ruta)
    assert respuesta.status_code == 302
    assert "/ingresar" in respuesta.headers["Location"]

# --- validación del pago ---
def test_datos_validos_no_tienen_errores():
    assert validar_pago(PAGO_VALIDO, HOY) == {}
    assert validar_pago(dict(PAGO_VALIDO, vencimiento="10/26"), HOY) == {}


@pytest.mark.parametrize("campo, valor, mensaje", [
    ("titular", "", "Ingresá el nombre del titular"),
    ("titular", "x" * 101, "hasta 100 caracteres"),
    ("numero", "", "Ingresá el número"),
    ("numero", "4242 abcd", "entre 13 y 19 dígitos"),
    ("numero", "4242", "entre 13 y 19 dígitos"),
    ("vencimiento", "1228", "MM/AA"),
    ("vencimiento", "09/26", "La tarjeta está vencida."),
    ("codigo_seguridad", "12", "3 o 4 dígitos"),
    ("codigo_seguridad", "12a", "3 o 4 dígitos"),
    ("acepto", "", "Tenés que aceptar"),
])
def test_cada_campo_invalido_tiene_su_mensaje(campo, valor, mensaje):
    errores = validar_pago(dict(PAGO_VALIDO, **{campo: valor}), HOY)
    assert list(errores) == [campo]
    assert mensaje in errores[campo]


def test_precio_usa_formato_argentino():
    assert precio(23000) == "$23.000"
    assert precio(6500.5) == "$6.500,50"
    assert precio(None) is None


# --- SCRUM-81: el checkout ofrece cancelar mientras se pueda ---
@pytest.mark.parametrize("cancelable, se_ofrece", [(True, True), (False, False)])
def test_compra_confirmada_ofrece_cancelar_solo_si_todavia_se_puede(cliente_logueado, cancelable, se_ofrece):
    with _api(compras=(dict(COMPRA_CONFIRMADA, cancelable=cancelable),)):
        html = cliente_logueado.get(RUTA_CONFIRMADA).get_data(as_text=True)
    assert ('href="/compras/1042/cancelar">Cancelar compra</a>' in html) is se_ofrece
