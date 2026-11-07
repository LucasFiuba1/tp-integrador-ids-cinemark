"""Pruebas del template maquetado de validar ingreso del backoffice (SCRUM-122)."""
import re

import pytest

from src.frontend.filtros import fecha_hora, hora
from src.frontend.validaciones import MAXIMO_CODIGO_QR


# --- pantalla ---
@pytest.mark.parametrize("metodo", ["get", "post"])
def test_validar_sin_sesion_redirige_al_login(cliente_frontend, metodo):
    respuesta = getattr(cliente_frontend, metodo)("/admin/validar")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_validar_sin_codigo_muestra_el_formulario_y_el_historial(cliente_admin):
    respuesta = cliente_admin.get("/admin/validar")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/validar" aria-current="page"' in html
    assert '<form method="post" action="/admin/validar" class="validar-formulario" novalidate>' in html
    assert 'name="codigo" value="" placeholder="CP-1042-D5" autocomplete="off" required autofocus' in html
    assert "resultado-vacio" in html
    assert re.search(r'data-etiqueta="Hora">\s*19:12\s*</td>', html)
    assert 'class="badge badge-ya_utilizada">Ya usada</span>' in html


def test_codigo_valido_muestra_los_datos_y_el_boton_de_confirmar(cliente_admin):
    html = cliente_admin.post("/admin/validar", data={"codigo": " CP-1042-D5 "}).get_data(as_text=True)
    assert "resultado-valido" in html
    assert "Entrada válida" in html
    for dato in ("La noche del telón", "24/10 · 19:30", "Paradiso Centro · Sala 1", "Lucas Berardi", "#1042"):
        assert f"<dd>{dato}</dd>" in html
    assert '<form method="post" action="/admin/validar/confirmar">' in html
    assert 'name="compra_id" value="1042"' in html


@pytest.mark.parametrize("codigo, mensaje", [
    ("CP-1038-B3", "Este QR ya se usó el 24/10 a las 19:10."),
    ("XX-0000", "El código no corresponde a ninguna entrada."),
])
def test_codigo_rechazado_muestra_el_motivo_sin_confirmar(cliente_admin, codigo, mensaje):
    html = cliente_admin.post("/admin/validar", data={"codigo": codigo}).get_data(as_text=True)
    assert "resultado-invalido" in html
    assert mensaje in html
    assert "/admin/validar/confirmar" not in html


@pytest.mark.parametrize("codigo, mensaje", [
    ("", "Ingresá o escaneá el código de la entrada."),
    ("x" * (MAXIMO_CODIGO_QR + 1), "El código es demasiado largo"),
])
def test_codigo_invalido_devuelve_400_con_el_error_en_el_campo(cliente_admin, codigo, mensaje):
    respuesta = cliente_admin.post("/admin/validar", data={"codigo": codigo})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert '<label class="campo campo-invalido">' in html
    assert mensaje in html
    assert "resultado-vacio" in html


@pytest.mark.parametrize("datos, mensaje", [
    ({"compra_id": "1042"}, "Ingreso confirmado"),
    ({"compra_id": "abc"}, "No se pudo confirmar"),
    ({}, "No se pudo confirmar"),
])
def test_confirmar_ingreso_avisa_y_vuelve_a_validar(cliente_admin, datos, mensaje):
    respuesta = cliente_admin.post("/admin/validar/confirmar", data=datos, follow_redirects=True)
    assert respuesta.request.path == "/admin/validar"
    assert mensaje in respuesta.get_data(as_text=True)


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
