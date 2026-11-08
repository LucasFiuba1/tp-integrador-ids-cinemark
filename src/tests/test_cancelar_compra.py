"""Pruebas de la página de cancelación desde el perfil y desde el enlace del email (SCRUM-70)."""
from unittest.mock import patch

import pytest


def _compra_confirmada(**cambios):
    compra = {
        "id": 1042,
        "estado": "confirmada",
        "pelicula": "La noche del telón",
        "poster_url": None,
        "local": "Paradiso Centro",
        "sala": "Sala 1",
        "funcion": "2026-10-24T19:30:00",
        "butacas": ["D5", "D6"],
        "subtotal_entradas": 11000.0,
        "servicios": [{"nombre": "Combo pochoclos grande", "cantidad": 1, "subtotal": 6500.0}],
        "total": 17500.0,
        "email": "ana@email.com",
        "utilizada_en": None,
        "cancelada_en": None,
        "cancelable": True,
        "cancelable_hasta": "2026-10-24T17:30:00",
    }
    compra.update(cambios)
    return compra


# --- /compras/<id>/cancelar (desde Mi perfil, requiere sesión) ---
@pytest.mark.parametrize("metodo", ["get", "post"])
def test_cancelar_desde_perfil_sin_sesion_redirige_al_login(cliente_frontend, metodo):
    respuesta = getattr(cliente_frontend, metodo)("/compras/1042/cancelar")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_get_cancelar_desde_perfil_muestra_resumen_y_formulario_sin_cancelar(cliente_logueado):
    with patch("src.frontend.routes.publico.llamar", return_value=(_compra_confirmada(), None)) as llamar:
        respuesta = cliente_logueado.get("/compras/1042/cancelar")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    llamar.assert_called_once_with("GET", "/api/compras/1042")
    for texto in ("La noche del telón", "Paradiso Centro", "Sala 1", "D5, D6", "$17.500", "#1042"):
        assert texto in html
    assert 'action="/compras/1042/cancelar"' in html
    assert "Sí, cancelar compra" in html
    assert 'href="/perfil">No, volver</a>' in html


def test_post_cancelar_desde_perfil_exitoso_redirige_al_perfil_con_aviso(cliente_logueado):
    with patch("src.frontend.routes.publico.llamar", return_value=({"id": 1042, "estado": "cancelada"}, None)) as llamar:
        respuesta = cliente_logueado.post("/compras/1042/cancelar")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/perfil"
    llamar.assert_called_once_with("POST", "/api/compras/1042/cancelar")


@pytest.mark.parametrize(
    "codigo, mensaje",
    [
        ("FUERA_DE_PLAZO", "No se puede cancelar: faltan menos de 2 horas para la función."),
        ("YA_UTILIZADA", "No se puede cancelar: la entrada ya fue utilizada."),
        ("YA_CANCELADA", "La compra ya fue cancelada."),
    ],
)
def test_post_cancelar_desde_perfil_con_conflicto_muestra_motivo_sin_boton(cliente_logueado, codigo, mensaje):
    respuestas = [
        (None, {"status": 409, "codigo": codigo, "mensaje": mensaje}),
        (_compra_confirmada(cancelable=False), None),
    ]
    with patch("src.frontend.routes.publico.llamar", side_effect=respuestas):
        respuesta = cliente_logueado.post("/compras/1042/cancelar")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert mensaje in html
    assert "Sí, cancelar compra" not in html


def test_get_cancelar_desde_perfil_con_error_redirige_al_perfil(cliente_logueado):
    error = {"status": 404, "codigo": "NO_ENCONTRADO", "mensaje": "La compra no existe."}
    with patch("src.frontend.routes.publico.llamar", return_value=(None, error)):
        respuesta = cliente_logueado.get("/compras/1042/cancelar")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/perfil"


# --- /cancelar/<token> (desde el email, accesible sin sesión) ---
def test_get_cancelar_por_token_funciona_sin_sesion_y_no_cancela_automaticamente(cliente_frontend):
    with patch("src.frontend.routes.publico.llamar", return_value=(_compra_confirmada(), None)) as llamar:
        respuesta = cliente_frontend.get("/cancelar/token-firmado")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    llamar.assert_called_once_with("GET", "/api/compras/por-token", params={"token": "token-firmado"})
    assert 'action="/cancelar/token-firmado"' in html
    assert "Sí, cancelar compra" in html
    assert 'href="/">No, volver</a>' in html


def test_get_cancelar_por_token_invalido_muestra_estado_de_error_400(cliente_frontend):
    error = {"status": 400, "codigo": "TOKEN_INVALIDO", "mensaje": "El enlace de cancelación no es válido o expiró."}
    with patch("src.frontend.routes.publico.llamar", return_value=(None, error)):
        respuesta = cliente_frontend.get("/cancelar/token-malo")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert "No pudimos abrir la compra" in html
    assert "El enlace de cancelación no es válido o expiró." in html
    assert "Sí, cancelar compra" not in html


def test_post_cancelar_por_token_exitoso_muestra_confirmacion_sin_sesion(cliente_frontend):
    respuestas = [
        ({"id": 1042, "estado": "cancelada"}, None),
        (_compra_confirmada(estado="cancelada", cancelable=False), None),
    ]
    with patch("src.frontend.routes.publico.llamar", side_effect=respuestas) as llamar:
        respuesta = cliente_frontend.post("/cancelar/token-firmado")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert llamar.call_args_list[0].args == ("POST", "/api/compras/cancelar-por-token")
    assert llamar.call_args_list[0].kwargs == {"json": {"token": "token-firmado"}}
    assert "Compra cancelada" in html
    assert "Liberamos las butacas y el QR de ingreso ya no es válido." in html
    assert "Sí, cancelar compra" not in html


@pytest.mark.parametrize(
    "cambios_compra, texto_esperado",
    [
        ({"cancelable": False}, "No se puede cancelar: faltan menos de 2 horas para la función."),
        ({"utilizada_en": "2026-10-24T19:15:00", "cancelable": False}, "No se puede cancelar: la entrada ya fue utilizada."),
        ({"estado": "cancelada", "cancelable": False}, "La compra ya fue cancelada."),
    ],
)
def test_get_cancelar_muestra_estado_cuando_no_es_cancelable(cliente_frontend, cambios_compra, texto_esperado):
    with patch("src.frontend.routes.publico.llamar", return_value=(_compra_confirmada(**cambios_compra), None)):
        respuesta = cliente_frontend.get("/cancelar/token-firmado")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert texto_esperado in html
    assert "Sí, cancelar compra" not in html


def test_post_cancelar_por_token_fuera_de_plazo_muestra_motivo_con_status_409(cliente_frontend):
    error = {"status": 409, "codigo": "FUERA_DE_PLAZO", "mensaje": "No se puede cancelar: faltan menos de 2 horas para la función."}
    respuestas = [(None, error), (_compra_confirmada(cancelable=False), None)]
    with patch("src.frontend.routes.publico.llamar", side_effect=respuestas):
        respuesta = cliente_frontend.post("/cancelar/token-firmado")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert "No se puede cancelar: faltan menos de 2 horas para la función." in html
    assert "Sí, cancelar compra" not in html
