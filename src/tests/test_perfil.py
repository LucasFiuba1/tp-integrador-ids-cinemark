"""Pruebas del perfil del cliente maquetado con datos de ejemplo (SCRUM-116)."""
from datetime import datetime
from unittest.mock import patch

import pytest

from src.frontend.filtros import dia_semana
from src.frontend.routes.publico import _pestana_compra


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
                  "Ver QR", "Pagar ahora", "Se puede cancelar hasta las 17:30",
                  "No se puede cancelar: faltan menos de 2 horas", "Las butacas se liberan a las 19:42 si no pagás",
                  "Películas que viste", "Se suman cuando se valida tu QR al ingresar a la sala.", "Vista el 18/10",
                  "Paradiso Centro · Sala 1 · Vie 20/11 · 19:30", "Butacas D5, D6, D7 · Combo pochoclos grande × 1"):
        assert texto in html
    for titulo in ("La noche del telón", "Código medianoche", "Pequeños gigantes"):
        assert _titulo_compra(titulo) in html
    assert 'href="/perfil?estado=proximas" aria-current="page">Próximas</a>' in html
    assert 'href="/compras/1042/cancelar"' in html and 'href="/compras/1044/pago"' in html
    assert 'class="boton boton-secundario boton-deshabilitado" aria-disabled="true">Cancelar' in html
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
