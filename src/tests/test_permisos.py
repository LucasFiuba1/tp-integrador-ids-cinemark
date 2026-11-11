"""Matriz de permisos endpoint × rol y robustez ante datos inválidos en la API (SCRUM-80).

- Cada endpoint de la API figura en MATRIZ con los roles que lo pueden usar. Una prueba recorre `app.url_map`
  y falla si aparece un endpoint nuevo sin cargar en la matriz, así nadie se olvida de definir su seguridad.
- Para cada endpoint y rol (anónimo / cliente / admin) se verifica el resultado esperado: 401 sin sesión,
  403 con un rol sin permiso y que el rol permitido pase la autenticación.
- Datos inválidos (cuerpo vacío o con otra forma, tipos incorrectos, negativos, textos muy largos, IDs
  inexistentes): siempre 4xx con el JSON de error {"error": {"codigo", "mensaje"}}, nunca 500.

La base está simulada (devuelve vacío / None) y TMDB no se llama: no hace falta MySQL ni internet.
"""
from unittest.mock import patch

import pytest

from src.tests.utilidades import afirmar_error_json, simular_bd

PUBLICO = ()
CLIENTE = ("cliente",)
ADMIN = ("admin",)
CLIENTE_Y_ADMIN = ("cliente", "admin")

# (método, ruta de ejemplo, regla de Flask, roles que la pueden usar). PUBLICO = no pide sesión.
# Las dos rutas "por-token" son públicas a propósito: las protege el token firmado del email (docs/endpoints.md).
MATRIZ = [
    ("GET", "/api/salud", "/api/salud", PUBLICO),
    ("POST", "/api/auth/registro", "/api/auth/registro", PUBLICO),
    ("POST", "/api/auth/login", "/api/auth/login", PUBLICO),
    ("GET", "/api/auth/me", "/api/auth/me", CLIENTE_Y_ADMIN),
    ("GET", "/api/locales", "/api/locales", PUBLICO),
    ("GET", "/api/cartelera", "/api/cartelera", PUBLICO),
    ("GET", "/api/peliculas/1", "/api/peliculas/<int:pelicula_id>", PUBLICO),
    ("GET", "/api/funciones/1", "/api/funciones/<int:funcion_id>", PUBLICO),
    ("GET", "/api/funciones/1/butacas", "/api/funciones/<int:funcion_id>/butacas", PUBLICO),
    ("GET", "/api/servicios", "/api/servicios", PUBLICO),
    ("POST", "/api/compras", "/api/compras", CLIENTE),
    ("GET", "/api/compras/1", "/api/compras/<int:compra_id>", CLIENTE_Y_ADMIN),
    ("PUT", "/api/compras/1/servicios", "/api/compras/<int:compra_id>/servicios", CLIENTE),
    ("POST", "/api/compras/1/confirmar", "/api/compras/<int:compra_id>/confirmar", CLIENTE),
    ("POST", "/api/compras/1/cancelar", "/api/compras/<int:compra_id>/cancelar", CLIENTE),
    ("GET", "/api/compras/por-token", "/api/compras/por-token", PUBLICO),
    ("POST", "/api/compras/cancelar-por-token", "/api/compras/cancelar-por-token", PUBLICO),
    ("GET", "/api/me/compras", "/api/me/compras", CLIENTE_Y_ADMIN),
    ("GET", "/api/me/peliculas-vistas", "/api/me/peliculas-vistas", CLIENTE_Y_ADMIN),
    ("GET", "/api/admin/locales", "/api/admin/locales", ADMIN),
    ("POST", "/api/admin/locales", "/api/admin/locales", ADMIN),
    ("PUT", "/api/admin/locales/1", "/api/admin/locales/<int:local_id>", ADMIN),
    ("DELETE", "/api/admin/locales/1", "/api/admin/locales/<int:local_id>", ADMIN),
    ("GET", "/api/admin/salas", "/api/admin/salas", ADMIN),
    ("POST", "/api/admin/salas", "/api/admin/salas", ADMIN),
    ("GET", "/api/admin/salas/1", "/api/admin/salas/<int:sala_id>", ADMIN),
    ("PUT", "/api/admin/salas/1", "/api/admin/salas/<int:sala_id>", ADMIN),
    ("DELETE", "/api/admin/salas/1", "/api/admin/salas/<int:sala_id>", ADMIN),
    ("GET", "/api/admin/servicios", "/api/admin/servicios", ADMIN),
    ("POST", "/api/admin/servicios", "/api/admin/servicios", ADMIN),
    ("PUT", "/api/admin/servicios/1", "/api/admin/servicios/<int:servicio_id>", ADMIN),
    ("DELETE", "/api/admin/servicios/1", "/api/admin/servicios/<int:servicio_id>", ADMIN),
    ("POST", "/api/admin/servicios/1/reactivar", "/api/admin/servicios/<int:servicio_id>/reactivar", ADMIN),
    ("GET", "/api/admin/tmdb/buscar", "/api/admin/tmdb/buscar", ADMIN),
    ("GET", "/api/admin/peliculas", "/api/admin/peliculas", ADMIN),
    ("POST", "/api/admin/peliculas", "/api/admin/peliculas", ADMIN),
    ("GET", "/api/admin/peliculas/1", "/api/admin/peliculas/<int:pelicula_id>", ADMIN),
    ("PATCH", "/api/admin/peliculas/1", "/api/admin/peliculas/<int:pelicula_id>", ADMIN),
    ("DELETE", "/api/admin/peliculas/1", "/api/admin/peliculas/<int:pelicula_id>", ADMIN),
    ("GET", "/api/admin/funciones", "/api/admin/funciones", ADMIN),
    ("POST", "/api/admin/funciones", "/api/admin/funciones", ADMIN),
    ("PUT", "/api/admin/funciones/1", "/api/admin/funciones/<int:funcion_id>", ADMIN),
    ("DELETE", "/api/admin/funciones/1", "/api/admin/funciones/<int:funcion_id>", ADMIN),
    ("GET", "/api/admin/dashboards/ocupacion", "/api/admin/dashboards/ocupacion", ADMIN),
    ("GET", "/api/admin/dashboards/ventas-genero", "/api/admin/dashboards/ventas-genero", ADMIN),
    ("GET", "/api/admin/dashboards/franjas-horarias", "/api/admin/dashboards/franjas-horarias", ADMIN),
    ("GET", "/api/admin/dashboards/cancelaciones", "/api/admin/dashboards/cancelaciones", ADMIN),
    ("GET", "/api/admin/ingresos", "/api/admin/ingresos", ADMIN),
    ("POST", "/api/admin/ingresos/validar", "/api/admin/ingresos/validar", ADMIN),
]

SERVICES_CON_BD = (
    "src.backend.services.cartelera", "src.backend.services.compras", "src.backend.services.cuentas",
    "src.backend.services.dashboards", "src.backend.services.funciones", "src.backend.services.ingresos",
    "src.backend.services.peliculas", "src.backend.services.perfil",
)


def _id(caso):
    return f"{caso[0]} {caso[1]}"


def _con_sesion(roles):
    return [caso for caso in MATRIZ if caso[3] and set(roles) - set(caso[3])]


def _pedir(cliente, metodo, ruta, cabeceras=None, **opciones):
    return cliente.open(ruta, method=metodo, headers=cabeceras or {}, **opciones)


@pytest.fixture
def bd():
    """Base vacía en todos los services y TMDB cortado: ninguna prueba sale de la máquina."""
    with simular_bd(destinos=SERVICES_CON_BD) as simulacion, patch(
        "src.backend.services.tmdb.requests.get", side_effect=AssertionError("La prueba intentó llamar a TMDB.")
    ):
        yield simulacion


# --- la matriz cubre toda la API ---
def test_matriz_cubre_todos_los_endpoints_de_la_api(app_backend):
    registrados = {
        (metodo, regla.rule)
        for regla in app_backend.url_map.iter_rules()
        if regla.rule.startswith("/api/")
        for metodo in regla.methods - {"HEAD", "OPTIONS"}
    }
    en_matriz = {(metodo, regla) for metodo, _, regla, _ in MATRIZ}
    assert registrados - en_matriz == set(), "Endpoints sin cargar en MATRIZ (definir sus roles)."
    assert en_matriz - registrados == set(), "MATRIZ tiene endpoints que ya no existen."


def test_solo_salud_login_registro_cartelera_y_tokens_del_email_son_publicos():
    publicos = {ruta for _, ruta, _, roles in MATRIZ if roles == PUBLICO}
    assert publicos == {
        "/api/salud", "/api/auth/registro", "/api/auth/login", "/api/locales", "/api/cartelera",
        "/api/peliculas/1", "/api/funciones/1", "/api/funciones/1/butacas", "/api/servicios",
        "/api/compras/por-token", "/api/compras/cancelar-por-token",
    }


# --- anónimo ---
@pytest.mark.parametrize("caso", [caso for caso in MATRIZ if caso[3]], ids=_id)
def test_endpoint_protegido_sin_token_devuelve_401(cliente_backend, bd, caso):
    metodo, ruta, _, _ = caso
    afirmar_error_json(_pedir(cliente_backend, metodo, ruta, json={}), 401, "NO_AUTENTICADO")
    bd.consultar.assert_not_called()


@pytest.mark.parametrize("caso", [caso for caso in MATRIZ if caso[3]], ids=_id)
@pytest.mark.parametrize("encabezado", ["Bearer token-trucho", "Basic abc", "Bearer "])
def test_endpoint_protegido_con_token_invalido_devuelve_401(cliente_backend, bd, caso, encabezado):
    metodo, ruta, _, _ = caso
    respuesta = _pedir(cliente_backend, metodo, ruta, {"Authorization": encabezado}, json={})
    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] in ("NO_AUTENTICADO", "TOKEN_INVALIDO")


@pytest.mark.parametrize("caso", [caso for caso in MATRIZ if not caso[3]], ids=_id)
def test_endpoint_publico_sin_token_no_pide_sesion(cliente_backend, bd, caso):
    metodo, ruta, _, _ = caso
    assert _pedir(cliente_backend, metodo, ruta, json={}).status_code not in (401, 403)


# --- rol sin permiso ---
@pytest.mark.parametrize("caso", _con_sesion(CLIENTE), ids=_id)
def test_cliente_en_endpoint_de_admin_devuelve_403(cliente_backend, cabeceras_cliente, bd, caso):
    metodo, ruta, _, _ = caso
    afirmar_error_json(_pedir(cliente_backend, metodo, ruta, cabeceras_cliente, json={}), 403, "SIN_PERMISO")
    bd.transaccion.assert_not_called()


@pytest.mark.parametrize("caso", _con_sesion(ADMIN), ids=_id)
def test_admin_en_endpoint_solo_de_cliente_devuelve_403(cliente_backend, cabeceras_admin, bd, caso):
    """Comprar, elegir servicios, confirmar y cancelar son acciones del cliente sobre sus propias compras."""
    metodo, ruta, _, _ = caso
    afirmar_error_json(_pedir(cliente_backend, metodo, ruta, cabeceras_admin, json={}), 403, "SIN_PERMISO")


# --- rol permitido ---
PERMITIDOS = [pytest.param(caso, rol, id=f"{rol} {_id(caso)}") for caso in MATRIZ for rol in caso[3]]


@pytest.mark.parametrize("caso, rol", PERMITIDOS)
def test_rol_permitido_pasa_la_autenticacion_y_nunca_da_500(
    cliente_backend, cabeceras_cliente, cabeceras_admin, bd, caso, rol
):
    metodo, ruta, _, _ = caso
    cabeceras = cabeceras_admin if rol == "admin" else cabeceras_cliente
    respuesta = _pedir(cliente_backend, metodo, ruta, cabeceras, json={})
    assert respuesta.status_code not in (401, 403, 500), respuesta.get_json()


# --- datos inválidos: nunca 500 ---
TEXTO_LARGO = "x" * 5000
CUERPOS_INVALIDOS = [
    pytest.param(None, id="sin_cuerpo"),
    pytest.param([], id="lista"),
    pytest.param("texto", id="texto"),
    pytest.param({}, id="objeto_vacio"),
    pytest.param({"nombre": "", "email": "", "password": ""}, id="campos_vacios"),
    pytest.param({"nombre": 123, "direccion": True, "precio": "caro", "filas": "diez"}, id="tipos_incorrectos"),
    pytest.param({"nombre": "Sala", "filas": -5, "columnas": -1, "precio": -10, "local_id": -1}, id="negativos"),
    pytest.param({"nombre": TEXTO_LARGO, "direccion": TEXTO_LARGO, "email": TEXTO_LARGO}, id="textos_largos"),
    pytest.param({"butacas": "A1", "funcion_id": "uno", "fecha_hora": "mañana"}, id="formatos_invalidos"),
]
ESCRITURAS = [caso for caso in MATRIZ if caso[0] in ("POST", "PUT", "PATCH")]


def _cabeceras_para(roles, cabeceras_cliente, cabeceras_admin):
    if not roles:
        return {}
    return cabeceras_cliente if "cliente" in roles else cabeceras_admin


@pytest.mark.parametrize("cuerpo", CUERPOS_INVALIDOS)
@pytest.mark.parametrize("caso", ESCRITURAS, ids=_id)
def test_cuerpo_invalido_devuelve_error_4xx_en_json(
    cliente_backend, cabeceras_cliente, cabeceras_admin, bd, caso, cuerpo
):
    metodo, ruta, _, roles = caso
    cabeceras = _cabeceras_para(roles, cabeceras_cliente, cabeceras_admin)
    opciones = {"data": "{no es json", "content_type": "application/json"} if cuerpo is None else {"json": cuerpo}
    respuesta = _pedir(cliente_backend, metodo, ruta, cabeceras, **opciones)
    assert 400 <= respuesta.status_code < 500, respuesta.get_json()
    error = respuesta.get_json()["error"]
    assert error["codigo"] and error["mensaje"]


@pytest.mark.parametrize("caso", [caso for caso in MATRIZ if "/1" in caso[1]], ids=_id)
def test_id_inexistente_devuelve_4xx_y_nunca_500(cliente_backend, cabeceras_cliente, cabeceras_admin, bd, caso):
    """Con la base vacía ningún ID existe: el endpoint responde 404 (o 400 si el cuerpo vacío no alcanza)."""
    metodo, ruta, _, roles = caso
    cabeceras = _cabeceras_para(roles, cabeceras_cliente, cabeceras_admin)
    respuesta = _pedir(cliente_backend, metodo, ruta.replace("/1", "/987654", 1), cabeceras, json={})
    assert respuesta.status_code in (400, 404), respuesta.get_json()


@pytest.mark.parametrize("ruta", ["/api/peliculas/-1", "/api/funciones/abc/butacas", "/api/admin/salas/1.5"])
def test_id_que_no_es_entero_positivo_devuelve_404_en_json(cliente_backend, cabeceras_admin, ruta):
    afirmar_error_json(cliente_backend.get(ruta, headers=cabeceras_admin), 404, "NO_ENCONTRADO")


@pytest.mark.parametrize("parametros", [
    "local_id=abc", "local_id=-3", "local_id=0", "local_id=²", "fecha=ayer", "fecha=2026-13-45",
])
def test_cartelera_con_filtros_invalidos_devuelve_400(cliente_backend, bd, parametros):
    afirmar_error_json(cliente_backend.get(f"/api/cartelera?{parametros}"), 400, "DATOS_INVALIDOS")


@pytest.mark.parametrize("parametros", ["desde=ayer", "hasta=2026-02-30", "local_id=xx", "desde=2026-12-01&hasta=2026-11-01"])
@pytest.mark.parametrize("tablero", ["ocupacion", "ventas-genero", "franjas-horarias", "cancelaciones"])
def test_dashboards_con_filtros_invalidos_devuelven_400(cliente_backend, cabeceras_admin, bd, tablero, parametros):
    respuesta = cliente_backend.get(f"/api/admin/dashboards/{tablero}?{parametros}", headers=cabeceras_admin)
    afirmar_error_json(respuesta, 400, "DATOS_INVALIDOS")


def test_metodo_no_permitido_devuelve_405_en_json(cliente_backend):
    afirmar_error_json(cliente_backend.delete("/api/cartelera"), 405, "METODO_NO_PERMITIDO")


def test_ruta_inexistente_devuelve_404_en_json(cliente_backend):
    afirmar_error_json(cliente_backend.get("/api/no-existe"), 404, "NO_ENCONTRADO")


# --- un cliente no ve ni toca compras de otro ---
def _compra_de_otro(bd):
    """La compra 1 es del usuario 99: ni la consulta ni el FOR UPDATE la devuelven como propia del cliente (id 2)."""
    fila = {"id": 1, "usuario_id": 99, "estado": "confirmada", "utilizada_en": None, "total": 10, "vencida": 0}
    bd.cursor.fetchone.return_value = fila
    bd.consultar_uno.return_value = fila


@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("POST", "/api/compras/1/cancelar", None),
    ("POST", "/api/compras/1/confirmar", None),
    ("PUT", "/api/compras/1/servicios", []),
])
def test_cliente_no_puede_operar_la_compra_de_otro(cliente_backend, cabeceras_cliente, bd, metodo, ruta, cuerpo):
    _compra_de_otro(bd)
    respuesta = _pedir(cliente_backend, metodo, ruta, cabeceras_cliente, json=cuerpo)
    afirmar_error_json(respuesta, 403, "SIN_PERMISO")
    sentencias = [str(llamada.args[0]).lstrip() for llamada in bd.cursor.execute.call_args_list]
    assert not any(sql.startswith(("UPDATE", "INSERT", "DELETE")) for sql in sentencias)
    bd.ejecutar.assert_not_called()


def test_cliente_no_puede_ver_la_compra_de_otro(cliente_backend, cabeceras_cliente, bd):
    _compra_de_otro(bd)
    afirmar_error_json(cliente_backend.get("/api/compras/1", headers=cabeceras_cliente), 403, "SIN_PERMISO")
    bd.consultar.assert_not_called()


def test_perfil_lista_solo_las_compras_del_usuario_del_token(cliente_backend, cabeceras_cliente, bd):
    cliente_backend.get("/api/me/compras", headers=cabeceras_cliente)
    for llamada in bd.consultar.call_args_list:
        assert 2 in llamada.args[1]
