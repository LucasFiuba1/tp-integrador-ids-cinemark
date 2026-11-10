"""Pruebas del ABM de servicios del backoffice (SCRUM-72)."""
from unittest.mock import patch

import pytest

from src.frontend.filtros import precio
from src.frontend.validaciones import (
    MAXIMO_DESCRIPCION,
    MAXIMO_NOMBRE,
    validar_servicio,
)

SERVICIO_VALIDO = {
    "nombre": "Combo familiar",
    "descripcion": "Dos pochoclos y dos gaseosas",
    "precio": "9500",
}


@pytest.fixture
def api_servicios():
    servicios = [
        {"id": 1, "nombre": "Combo pochoclos grande", "descripcion": "Pochoclos", "precio": 6500, "activo": True},
        {"id": 2, "nombre": "Gaseosa", "descripcion": "Gaseosa de 500 ml", "precio": 2500, "activo": True},
        {"id": 3, "nombre": "Combo premium", "descripcion": "Combo especial", "precio": 8000, "activo": True},
        {"id": 4, "nombre": "Servicio inactivo", "descripcion": "", "precio": 1000, "activo": False},
    ]

    def simular_llamada(metodo, ruta, json=None, params=None):
        if metodo == "GET" and ruta == "/api/admin/servicios":
            return servicios, None
        if metodo == "POST" and ruta.endswith("/reactivar"):
            return None, None
        if metodo in ("POST", "PUT"):
            return {"nombre": json["nombre"]}, None
        if metodo == "DELETE":
            return None, None
        return None, {"status": 404, "codigo": "NO_ENCONTRADO", "mensaje": "No encontrado"}

    with patch("src.frontend.routes.backoffice.llamar", side_effect=simular_llamada) as llamada:
        yield llamada


# --- Pantallas y acciones ---
@pytest.mark.parametrize("metodo, ruta", [
    ("get", "/admin/servicios"),
    ("post", "/admin/servicios"),
    ("get", "/admin/servicios/1"),
    ("post", "/admin/servicios/1/baja"),
])
def test_servicios_sin_sesion_redirige_al_login(cliente_frontend, metodo, ruta):
    respuesta = getattr(cliente_frontend, metodo)(ruta)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_listado_muestra_los_servicios_con_precio_estado_y_acciones(cliente_admin, api_servicios):
    respuesta = cliente_admin.get("/admin/servicios")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/servicios" aria-current="page"' in html
    assert 'href="/admin/servicios#formulario-servicio">Nuevo servicio</a>' in html
    for dato in ("Combo pochoclos grande", "Gaseosa de 500 ml", "$6.500", "$8.000"):
        assert dato in html
    assert html.count('class="badge badge-activa">Activo</span>') == 3
    assert 'class="badge badge-inactiva">Inactivo</span>' in html
    assert 'href="/admin/servicios/4">Editar</a>' in html
    assert 'action="/admin/servicios/1/baja"' in html
    assert 'action="/admin/servicios/4/baja"' not in html
    assert '>Quitar</button>' in html
    assert 'onsubmit="return confirm(' in html
    api_servicios.assert_called_with("GET", "/api/admin/servicios")


def test_formulario_de_alta_vacio(cliente_admin, api_servicios):
    html = cliente_admin.get("/admin/servicios").get_data(as_text=True)
    assert ">Nuevo servicio</h2>" in html
    assert '<form method="post" action="/admin/servicios" class="formulario-linea" novalidate>' in html
    assert 'type="number" name="precio" value="" placeholder="$0"' in html
    assert ">Cancelar</a>" not in html


def test_editar_carga_el_servicio_en_el_formulario(cliente_admin, api_servicios):
    respuesta = cliente_admin.get("/admin/servicios/2")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert ">Editar Gaseosa</h2>" in html
    assert '<form method="post" action="/admin/servicios/2" class="formulario-linea" novalidate>' in html
    assert 'name="descripcion" value="Gaseosa de 500 ml"' in html
    assert 'name="precio" value="2500"' in html
    assert 'href="/admin/servicios">Cancelar</a>' in html


def test_editar_un_servicio_inexistente_vuelve_al_listado_con_aviso(cliente_admin, api_servicios):
    respuesta = cliente_admin.get("/admin/servicios/99", follow_redirects=True)
    assert respuesta.request.path == "/admin/servicios"
    assert "Ese servicio no existe." in respuesta.get_data(as_text=True)


@pytest.mark.parametrize("ruta, metodo, api_ruta", [
    ("/admin/servicios", "POST", "/api/admin/servicios"),
    ("/admin/servicios/1", "PUT", "/api/admin/servicios/1"),
])
def test_guardar_un_servicio_valido_vuelve_al_listado(cliente_admin, api_servicios, ruta, metodo, api_ruta):
    respuesta = cliente_admin.post(ruta, data=SERVICIO_VALIDO, follow_redirects=True)
    assert respuesta.request.path == "/admin/servicios"
    assert "El servicio se guardó correctamente." in respuesta.get_data(as_text=True)
    api_servicios.assert_any_call(
        metodo,
        api_ruta,
        json={"nombre": "Combo familiar", "descripcion": "Dos pochoclos y dos gaseosas", "precio": 9500.0},
    )


def test_guardar_un_servicio_invalido_devuelve_400_con_los_errores(cliente_admin, api_servicios):
    respuesta = cliente_admin.post("/admin/servicios", data={"nombre": " ", "descripcion": "", "precio": "abc"})
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert "Ingresá el nombre del servicio." in html
    assert "El precio tiene que ser un número" in html
    assert 'name="precio" value="abc"' in html
    assert all(llamada.args[0] == "GET" for llamada in api_servicios.call_args_list)


def test_quitar_un_servicio_avisa_y_vuelve_al_listado(cliente_admin, api_servicios):
    respuesta = cliente_admin.post("/admin/servicios/3/baja", follow_redirects=True)
    assert respuesta.request.path == "/admin/servicios"
    assert "El servicio quedó inactivo." in respuesta.get_data(as_text=True)
    api_servicios.assert_any_call("DELETE", "/api/admin/servicios/3")


@pytest.mark.parametrize("estado, mensaje", [
    (400, "El precio debe ser mayor a cero."),
    (409, "Ya existe un servicio con ese nombre."),
])
def test_error_del_backend_se_muestra_en_el_formulario(cliente_admin, api_servicios, estado, mensaje):
    api_servicios.side_effect = lambda metodo, ruta, json=None, params=None: (
        (None, {"status": estado, "codigo": "ERROR", "mensaje": mensaje})
        if metodo == "POST" else ([], None)
    )
    respuesta = cliente_admin.post("/admin/servicios", data=SERVICIO_VALIDO)
    assert mensaje in respuesta.get_data(as_text=True)
    assert 'name="nombre" value="Combo familiar"' in respuesta.get_data(as_text=True)


# --- Validación ---
@pytest.mark.parametrize("cambios", [
    {"precio": "9500"},
    {"precio": "9500.50"},
    {"precio": "9500,50"},
    {"descripcion": ""},
])
def test_servicio_valido_no_tiene_errores(cambios):
    assert validar_servicio({**SERVICIO_VALIDO, **cambios}) == {}

@pytest.mark.parametrize("campo, valor, mensaje", [
    ("nombre", "", "Ingresá el nombre"),
    ("nombre", "x" * (MAXIMO_NOMBRE + 1), "hasta 100 caracteres"),
    ("descripcion", "x" * (MAXIMO_DESCRIPCION + 1), "hasta 255 caracteres"),
    ("precio", "", "Ingresá el precio"),
    ("precio", "doce", "tiene que ser un número"),
    ("precio", "0", "mayor a $0"),
    ("precio", "-10", "mayor a $0"),
    ("precio", "100000000", "menor a $100.000.000"),
])
def test_campos_invalidos(campo, valor, mensaje):
    errores = validar_servicio({**SERVICIO_VALIDO, campo: valor})
    assert list(errores) == [campo]
    assert mensaje in errores[campo]


def test_filtro_precio_formatea_en_pesos_y_tolera_valores_raros():
    assert precio(6500) == "$6.500"
    assert precio("1234567.5") == "$1.234.567,50"
    assert precio("no es número") == "no es número"
    assert precio(None) is None


def test_reactivar_servicio_avisa_y_vuelve_al_listado(cliente_admin, api_servicios):
    respuesta = cliente_admin.post("/admin/servicios/4/reactivar", follow_redirects=True)
    assert respuesta.request.path == "/admin/servicios"
    assert "El servicio quedó activo." in respuesta.get_data(as_text=True)
    api_servicios.assert_any_call("POST", "/api/admin/servicios/4/reactivar")