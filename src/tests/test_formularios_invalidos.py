"""Ninguna pantalla del sitio ni del backoffice rompe ante datos inválidos o errores del backend (SCRUM-80).

Recorre todas las rutas del frontend (`app.url_map`) y las pide con GET y POST:
- con formularios basura (vacíos, tipos incorrectos, negativos, textos muy largos, IDs inexistentes);
- con el backend respondiendo un error 400/404/409 en JSON, o sin responder (caído).
En todos los casos la respuesta tiene que ser una página amigable o un redirect (nunca un 500 ni un traceback).
"""
from unittest.mock import Mock, patch

import pytest
import requests

from src.frontend.app import create_app

TEXTO_LARGO = "x" * 5000
FORMULARIOS = [
    pytest.param({}, id="vacio"),
    pytest.param({"nombre": "", "email": "", "password": "", "precio": "", "filas": ""}, id="campos_vacios"),
    pytest.param({"nombre": "Sala", "filas": "diez", "columnas": "-3", "precio": "caro", "local_id": "abc",
                  "sala_id": "-1", "pelicula_id": "x", "fecha_hora": "mañana", "butacas": "zz"}, id="tipos_incorrectos"),
    pytest.param({"nombre": TEXTO_LARGO, "direccion": TEXTO_LARGO, "email": TEXTO_LARGO,
                  "descripcion": TEXTO_LARGO, "token": TEXTO_LARGO}, id="textos_largos"),
    pytest.param({"butacas": ["999999", "-1"], "funcion_id": "987654", "tmdb_id": "0", "servicio_1": "-4"},
                 id="ids_inexistentes"),
]


def _respuesta_backend(status, codigo):
    respuesta = Mock(ok=False, status_code=status, content=b"x")
    respuesta.json.return_value = {"error": {"codigo": codigo, "mensaje": "Mensaje del backend."}}
    return respuesta


BACKENDS = [
    pytest.param({"side_effect": requests.ConnectionError()}, id="backend_caido"),
    pytest.param({"return_value": _respuesta_backend(400, "DATOS_INVALIDOS")}, id="backend_400"),
    pytest.param({"return_value": _respuesta_backend(404, "NO_ENCONTRADO")}, id="backend_404"),
    pytest.param({"return_value": _respuesta_backend(409, "CONFLICTO")}, id="backend_409"),
]
VALORES_DE_EJEMPLO = {"int": "987654", "default": "token-trucho"}


def _rutas_del_frontend():
    """(método, url de ejemplo) para cada ruta del frontend, con los parámetros de la URL completados."""
    casos = []
    for regla in create_app().url_map.iter_rules():
        if regla.endpoint == "static":
            continue
        url = regla.rule
        for argumento in regla.arguments:
            tipo = regla._converters[argumento].__class__.__name__.replace("Converter", "").lower()
            url = url.replace(f"<{argumento}>", VALORES_DE_EJEMPLO["default"])
            url = url.replace(f"<{tipo}:{argumento}>", VALORES_DE_EJEMPLO.get(tipo, VALORES_DE_EJEMPLO["default"]))
        casos += [pytest.param(metodo, url, id=f"{metodo} {url}") for metodo in sorted(regla.methods & {"GET", "POST"})]
    return casos


RUTAS = _rutas_del_frontend()


def _cliente_con_sesion(cliente_frontend, url):
    rol = "admin" if url.startswith("/admin") else "cliente"
    with cliente_frontend.session_transaction() as sesion:
        sesion.update(token=f"token-{rol}", rol=rol, nombre="Prueba")
    return cliente_frontend


def _afirmar_que_no_rompe(respuesta):
    """Una página amigable (incluso un 503 "el servidor no responde") vale; un 500 o un traceback, no."""
    assert respuesta.status_code != 500, respuesta.get_data(as_text=True)[:500]
    assert "Traceback" not in respuesta.get_data(as_text=True)


def test_hay_rutas_del_frontend_para_recorrer():
    assert any(url.startswith("/admin") for _, url in (caso.values for caso in RUTAS))
    assert any(metodo == "POST" for metodo, _ in (caso.values for caso in RUTAS))


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("metodo, url", RUTAS)
def test_pantalla_con_error_del_backend_no_rompe(cliente_frontend, metodo, url, backend):
    cliente = _cliente_con_sesion(cliente_frontend, url)
    with patch("src.frontend.api_client.requests.request", **backend):
        _afirmar_que_no_rompe(cliente.open(url, method=metodo, data={}))


@pytest.mark.parametrize("formulario", FORMULARIOS)
@pytest.mark.parametrize("metodo, url", [ruta for ruta in RUTAS if ruta.values[0] == "POST"])
def test_formulario_con_datos_invalidos_no_rompe(cliente_frontend, metodo, url, formulario):
    cliente = _cliente_con_sesion(cliente_frontend, url)
    with patch("src.frontend.api_client.requests.request", return_value=_respuesta_backend(400, "DATOS_INVALIDOS")):
        _afirmar_que_no_rompe(cliente.post(url, data=formulario))


@pytest.mark.parametrize("parametros", ["local_id=abc", "fecha=ayer", "local_id=-1&fecha=2026-99-99", "q=" + TEXTO_LARGO])
@pytest.mark.parametrize("url", ["/", "/peliculas/1", "/admin/", "/admin/dashboards", "/admin/funciones", "/admin/peliculas"])
def test_filtros_por_url_invalidos_no_rompen(cliente_frontend, url, parametros):
    cliente = _cliente_con_sesion(cliente_frontend, url)
    with patch("src.frontend.api_client.requests.request", return_value=_respuesta_backend(400, "DATOS_INVALIDOS")):
        _afirmar_que_no_rompe(cliente.get(f"{url}?{parametros}"))


@pytest.mark.parametrize("url", ["/perfil", "/mis-compras", "/compras/1/pago", "/compras/1/servicios"])
def test_pantalla_de_cliente_sin_sesion_redirige_al_login(cliente_frontend, url):
    respuesta = cliente_frontend.get(url)
    assert respuesta.status_code == 302
    assert "/ingresar" in respuesta.headers["Location"]


@pytest.mark.parametrize("url", ["/admin/", "/admin/locales", "/admin/funciones", "/admin/dashboards", "/admin/ingreso"])
def test_backoffice_con_sesion_de_cliente_no_se_muestra(cliente_logueado, url):
    with patch("src.frontend.api_client.requests.request") as peticion:
        respuesta = cliente_logueado.get(url)
    assert respuesta.status_code in (302, 403)
    peticion.assert_not_called()
