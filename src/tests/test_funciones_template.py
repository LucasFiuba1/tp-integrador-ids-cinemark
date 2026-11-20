"""Pruebas de programación de funciones del backoffice (SCRUM-57)."""
from unittest.mock import call, patch

import pytest


LOCALES = [
    {"id": 1, "nombre": "Paradiso Centro", "activa": True},
    {"id": 2, "nombre": "Paradiso Belgrano", "activa": True},
]

SALAS = {
    1: [
        {"id": 1, "local_id": 1, "nombre": "Sala 1", "activa": True},
        {"id": 2, "local_id": 1, "nombre": "Sala 2", "activa": True},
    ],
    2: [
        {"id": 3, "local_id": 2, "nombre": "Sala 1", "activa": True},
    ],
}

PELICULAS = [
    {"id": 1, "titulo": "Casablanca", "activa": True},
    {"id": 2, "titulo": "Toy Story", "activa": True},
]

FUNCIONES = [
    {
        "id": 1,
        "pelicula_id": 1,
        "pelicula": "Casablanca",
        "sala_id": 1,
        "sala": "Sala 1",
        "local_id": 1,
        "local": "Paradiso Centro",
        "fecha_hora": "2026-11-20T20:00:00",
        "precio": 6000.0,
        "activa": True,
    },
    {
        "id": 2,
        "pelicula_id": 2,
        "pelicula": "Toy Story",
        "sala_id": 3,
        "sala": "Sala 1",
        "local_id": 2,
        "local": "Paradiso Belgrano",
        "fecha_hora": "2026-11-21T18:30:00",
        "precio": 5500.0,
        "activa": True,
    },
    {
        "id": 3,
        "pelicula_id": 1,
        "pelicula": "Casablanca inactiva",
        "sala_id": 2,
        "sala": "Sala 2",
        "local_id": 1,
        "local": "Paradiso Centro",
        "fecha_hora": "2026-11-22T20:00:00",
        "precio": 6000.0,
        "activa": False,
    },
]


def _api_simulada(metodo, ruta, json=None, params=None):
    if metodo == "GET" and ruta == "/api/admin/locales":
        return LOCALES, None

    if metodo == "GET" and ruta == "/api/admin/peliculas":
        return PELICULAS, None

    if metodo == "GET" and ruta == "/api/admin/salas":
        local_id = (params or {}).get("local_id")
        return SALAS.get(local_id, []), None

    if metodo == "GET" and ruta == "/api/admin/funciones":
        return FUNCIONES, None

    if metodo == "POST" and ruta == "/api/admin/funciones":
        return FUNCIONES[0], None

    if metodo == "PUT" and ruta.startswith("/api/admin/funciones/"):
        return FUNCIONES[0], None

    if metodo == "DELETE" and ruta.startswith("/api/admin/funciones/"):
        return {"id": 1, "baja": "logica"}, None

    raise AssertionError(f"Llamada no simulada: {metodo} {ruta}")


@pytest.fixture
def api_funciones():
    with patch(
        "src.frontend.routes.backoffice.llamar",
        side_effect=_api_simulada,
    ) as llamar:
        yield llamar


# --- permisos ---


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/admin/funciones"),
        ("post", "/admin/funciones"),
        ("get", "/admin/funciones/1"),
        ("post", "/admin/funciones/1"),
        ("post", "/admin/funciones/1/baja"),
    ],
)
def test_funciones_sin_sesion_redirige_al_login(
    cliente_frontend,
    metodo,
    ruta,
):
    respuesta = getattr(cliente_frontend, metodo)(ruta)

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/admin/funciones"),
        ("post", "/admin/funciones"),
        ("get", "/admin/funciones/1"),
        ("post", "/admin/funciones/1"),
        ("post", "/admin/funciones/1/baja"),
    ],
)
def test_funciones_con_cliente_devuelve_403(
    cliente_logueado,
    metodo,
    ruta,
):
    respuesta = getattr(cliente_logueado, metodo)(ruta)

    assert respuesta.status_code == 403


# --- listado ---


def test_funciones_muestra_datos_de_la_api(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.get("/admin/funciones")
    html = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "Casablanca" in html
    assert "Toy Story" in html
    assert "Paradiso Centro" in html
    assert "Sala 1" in html
    assert "$6.000" in html


def test_funciones_no_muestra_funciones_inactivas(
    cliente_admin,
    api_funciones,
):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)

    assert "Casablanca inactiva" not in html


def test_funciones_usa_datetime_local(
    cliente_admin,
    api_funciones,
):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)

    assert 'type="datetime-local" name="fecha_hora"' in html
    assert 'type="number" name="precio"' in html


def test_funciones_no_muestra_columna_libres(
    cliente_admin,
    api_funciones,
):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)

    assert 'data-etiqueta="Libres"' not in html


def test_funciones_ofrece_editar_y_quitar(
    cliente_admin,
    api_funciones,
):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)

    assert 'href="/admin/funciones/1">Editar</a>' in html
    assert 'action="/admin/funciones/1/baja"' in html
    assert ">Quitar</button>" in html


# --- filtros ---


def test_funciones_filtra_por_local_y_fecha(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.get(
        "/admin/funciones",
        query_string={
            "local_id": "2",
            "fecha": "2026-11-21",
        },
    )

    assert respuesta.status_code == 200

    assert call(
        "GET",
        "/api/admin/salas",
        params={"local_id": 2},
    ) in api_funciones.call_args_list

    assert call(
        "GET",
        "/api/admin/funciones",
        params={
            "local_id": 2,
            "desde": "2026-11-21T00:00:00",
            "hasta": "2026-11-21T23:59:59",
        },
    ) in api_funciones.call_args_list


def test_funciones_local_inexistente_usa_el_primero(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.get(
        "/admin/funciones",
        query_string={"local_id": "999"},
    )

    assert respuesta.status_code == 200

    assert call(
        "GET",
        "/api/admin/salas",
        params={"local_id": 1},
    ) in api_funciones.call_args_list


# --- alta ---


def test_crear_funcion_llama_al_backend(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.post(
        "/admin/funciones",
        data={
            "pelicula_id": "1",
            "local_id": "1",
            "sala_id": "1",
            "fecha_hora": "2026-11-25T20:30",
            "precio": "6500",
        },
    )

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/funciones"

    api_funciones.assert_any_call(
        "POST",
        "/api/admin/funciones",
        json={
            "pelicula_id": 1,
            "sala_id": 1,
            "fecha_hora": "2026-11-25T20:30:00",
            "precio": 6500.0,
        },
    )


def test_crear_funcion_muestra_error_de_solapamiento(
    cliente_admin,
):
    def api(metodo, ruta, json=None, params=None):
        if metodo == "POST" and ruta == "/api/admin/funciones":
            return None, {
                "status": 409,
                "codigo": "FUNCION_SUPERPUESTA",
                "mensaje": "Ya hay una función superpuesta en esa sala.",
            }

        return _api_simulada(metodo, ruta, json, params)

    with patch(
        "src.frontend.routes.backoffice.llamar",
        side_effect=api,
    ):
        respuesta = cliente_admin.post(
            "/admin/funciones",
            data={
                "pelicula_id": "1",
                "local_id": "1",
                "sala_id": "1",
                "fecha_hora": "2026-11-25T20:30",
                "precio": "6500",
            },
        )

    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert "Ya hay una función superpuesta en esa sala." in html
    # SCRUM-81: el formulario conserva lo que cargó el admin en vez de vaciarse.
    assert 'value="2026-11-25T20:30"' in html
    assert 'value="6500"' in html
    assert '<option value="1" selected' in html


# --- edición ---


def test_editar_funcion_muestra_datos_actuales(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.get("/admin/funciones/1")
    html = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "Editar función" in html
    assert "Casablanca" in html
    assert 'value="2026-11-20T20:00"' in html
    assert 'value="6000.0"' in html


def test_editar_funcion_llama_put(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.post(
        "/admin/funciones/1",
        data={
            "pelicula_id": "1",
            "sala_id": "1",
            "fecha_hora": "2026-11-20T21:00",
            "precio": "7000",
        },
    )

    assert respuesta.status_code == 302

    api_funciones.assert_any_call(
        "PUT",
        "/api/admin/funciones/1",
        json={
            "pelicula_id": 1,
            "sala_id": 1,
            "fecha_hora": "2026-11-20T21:00:00",
            "precio": 7000.0,
        },
    )


# --- baja ---


def test_baja_funcion_llama_delete(
    cliente_admin,
    api_funciones,
):
    respuesta = cliente_admin.post("/admin/funciones/1/baja")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/funciones"

    api_funciones.assert_any_call(
        "DELETE",
        "/api/admin/funciones/1",
    )


def test_baja_funcion_con_entradas_muestra_error(
    cliente_admin,
):
    def api(metodo, ruta, json=None, params=None):
        if metodo == "DELETE" and ruta == "/api/admin/funciones/1":
            return None, {
                "status": 409,
                "codigo": "FUNCION_CON_ENTRADAS",
                "mensaje": (
                    "No se puede eliminar una función "
                    "con entradas registradas."
                ),
            }

        return _api_simulada(metodo, ruta, json, params)

    with patch(
        "src.frontend.routes.backoffice.llamar",
        side_effect=api,
    ):
        respuesta = cliente_admin.post(
            "/admin/funciones/1/baja",
            follow_redirects=True,
        )

    assert respuesta.status_code == 200
    assert (
        "No se puede eliminar una función con entradas registradas."
        in respuesta.get_data(as_text=True)
    )


# --- seguridad de Jinja ---


def test_funciones_escapa_texto_de_la_api(
    cliente_admin,
):
    funciones = [
        {
            **FUNCIONES[0],
            "pelicula": "<script>alert(1)</script>",
        }
    ]

    def api(metodo, ruta, json=None, params=None):
        if metodo == "GET" and ruta == "/api/admin/funciones":
            return funciones, None

        return _api_simulada(metodo, ruta, json, params)

    with patch(
        "src.frontend.routes.backoffice.llamar",
        side_effect=api,
    ):
        html = cliente_admin.get("/admin/funciones").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

# --- Regresiones que siguen siendo válidas ---


def _sesion(cliente, **datos):
    with cliente.session_transaction() as sesion:
        sesion.update(datos)
    return cliente


@pytest.mark.parametrize(
    "datos",
    [
        {"token": "t", "rol": "Admin"},
        {"token": "t", "rol": "ADMIN"},
        {"token": "t"},
        {"token": "t", "rol": ""},
        {"token": "t", "rol": None},
        {"token": "t", "rol": " admin"},
    ],
)
@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/admin/funciones"),
        ("post", "/admin/funciones"),
        ("get", "/admin/funciones/1"),
        ("post", "/admin/funciones/1"),
        ("post", "/admin/funciones/1/baja"),
    ],
)
def test_funciones_rechaza_roles_distintos_de_admin(
    cliente_frontend,
    datos,
    metodo,
    ruta,
):
    cliente = _sesion(cliente_frontend, **datos)
    assert getattr(cliente, metodo)(ruta).status_code == 403


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/admin/funciones"),
        ("post", "/admin/funciones"),
        ("get", "/admin/funciones/1"),
        ("post", "/admin/funciones/1"),
        ("post", "/admin/funciones/1/baja"),
    ],
)
def test_funciones_admin_sin_token_redirige_al_login(
    cliente_frontend,
    metodo,
    ruta,
):
    cliente = _sesion(cliente_frontend, rol="admin", token="")
    respuesta = getattr(cliente, metodo)(ruta)

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("put", "/admin/funciones"),
        ("delete", "/admin/funciones"),
        ("patch", "/admin/funciones"),
        ("delete", "/admin/funciones/1"),
        ("get", "/admin/funciones/1/baja"),
    ],
)
def test_funciones_con_verbo_incorrecto_devuelve_405(
    cliente_admin,
    metodo,
    ruta,
):
    assert getattr(cliente_admin, metodo)(ruta).status_code == 405


@pytest.mark.parametrize(
    "ruta",
    [
        "/admin/funciones/-1",
        "/admin/funciones/abc",
        "/admin/funciones/1.5",
        "/admin/funciones/abc/baja",
        "/admin/funciones//baja",
    ],
)
def test_funciones_con_id_no_entero_devuelve_404(cliente_admin, ruta):
    metodo = cliente_admin.post if ruta.endswith("/baja") else cliente_admin.get
    assert metodo(ruta).status_code == 404


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/admin/funciones/0"),
        ("post", "/admin/funciones/0/baja"),
        ("get", "/admin/funciones/999999999999"),
        ("post", "/admin/funciones/999999999999/baja"),
    ],
)
def test_funciones_con_id_inexistente_vuelve_al_listado(
    cliente_admin,
    api_funciones,
    metodo,
    ruta,
):
    respuesta = getattr(cliente_admin, metodo)(ruta)

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/funciones"

# --- SCRUM-81: el formulario se valida antes de llamar a la API (sin mensajes crudos del backend) ---
FUNCION_VALIDA = {"pelicula_id": "1", "local_id": "1", "sala_id": "1", "fecha_hora": "2026-11-25T20:30", "precio": "6500"}


def _llamadas_de_escritura(llamar):
    return [llamada for llamada in llamar.call_args_list if llamada.args[0] in ("POST", "PUT")]


@pytest.mark.parametrize("campo, valor, mensaje", [
    ("precio", "", "Ingresá el precio."),
    ("precio", "caro", "El precio tiene que ser un número, por ejemplo 2500."),
    ("precio", "0", "El precio tiene que ser mayor a $0 y menor a $100.000.000."),
    ("precio", "-10", "El precio tiene que ser mayor a $0 y menor a $100.000.000."),
    ("fecha_hora", "", "Ingresá la fecha y la hora de la función."),
    ("fecha_hora", "mañana", "Ingresá la fecha y la hora de la función."),
    ("pelicula_id", "", "Elegí la película."),
    ("sala_id", "x", "Elegí la sala."),
])
@pytest.mark.parametrize("url", ["/admin/funciones", "/admin/funciones/1"])
def test_funcion_con_datos_invalidos_muestra_el_error_sin_llamar_a_la_api(
    cliente_admin, api_funciones, url, campo, valor, mensaje,
):
    respuesta = cliente_admin.post(url, data={**FUNCION_VALIDA, campo: valor})

    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 400
    assert f'id="error-{campo}">{mensaje}<' in html
    assert _llamadas_de_escritura(api_funciones) == []


def test_crear_funcion_con_precio_con_coma_lo_manda_como_numero(cliente_admin, api_funciones):
    cliente_admin.post("/admin/funciones", data={**FUNCION_VALIDA, "precio": "6500,50"})

    assert _llamadas_de_escritura(api_funciones)[0].kwargs["json"]["precio"] == 6500.5


def test_editar_funcion_con_error_de_la_api_conserva_lo_cargado(cliente_admin):
    def api(metodo, ruta, json=None, params=None):
        if metodo == "PUT":
            return None, {"status": 409, "codigo": "FUNCION_SUPERPUESTA", "mensaje": "Ya hay una función superpuesta en esa sala."}
        return _api_simulada(metodo, ruta, json, params)

    with patch("src.frontend.routes.backoffice.llamar", side_effect=api):
        respuesta = cliente_admin.post("/admin/funciones/1", data={**FUNCION_VALIDA, "precio": "7100"})

    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 409
    assert "Ya hay una función superpuesta en esa sala." in html
    assert 'value="7100"' in html
