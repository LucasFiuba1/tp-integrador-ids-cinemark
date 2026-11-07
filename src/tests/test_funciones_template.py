"""Pruebas de la plantilla de programación de funciones del backoffice (SCRUM-119)."""
import pytest

RUTAS = [("get", "/admin/funciones"), ("post", "/admin/funciones"),
         ("get", "/admin/funciones/1"), ("post", "/admin/funciones/1/baja")]


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_funciones_sin_sesion_redirige_al_login(cliente_frontend, metodo, ruta):
    respuesta = getattr(cliente_frontend, metodo)(ruta)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_funciones_con_rol_cliente_devuelve_403(cliente_logueado, metodo, ruta):
    assert getattr(cliente_logueado, metodo)(ruta).status_code == 403


def test_funciones_con_admin_devuelve_200_con_sidebar_activo(cliente_admin):
    respuesta = cliente_admin.get("/admin/funciones")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'href="/admin/funciones" aria-current="page"' in html
    assert "Programación por local y sala" in html
    assert 'href="/admin/funciones#formulario-funcion">Nueva función</a>' in html
    assert "Esta sección está en construcción." not in html


def test_funciones_muestra_el_formulario_de_nueva_funcion(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert '<form method="post" action="/admin/funciones"' in html
    for nombre in ("pelicula_id", "local_id", "sala_id"):
        assert f'<select name="{nombre}"' in html
    for dato in ('type="date" name="fecha" value="2026-10-24"', 'type="time" name="hora" value="19:30"',
                 'type="number" name="precio" value="5500"', "Elegí una película", "Precio de la entrada",
                 ">Guardar función</button>", "El sistema valida que la sala esté libre en ese horario."):
        assert dato in html


def test_funciones_lista_las_funciones_con_fecha_precio_y_libres(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    for dato in ("La noche del telón", "Código Medianoche", "Pequeños gigantes", "Último tren a Lisboa",
                 "Paradiso Centro", "Paradiso Palermo", "Paradiso Belgrano", "Sala VIP",
                 "24/10 · 19:30", "24/10 · 22:15", "28/11 · 21:00", "29/11 · 15:00", "29/11 · 20:45",
                 "$5.500", "$9.500", "$6.000", "98 / 132", "120 / 132", "18 / 36", "84 / 96", "70 / 96"):
        assert dato in html


def test_funciones_ofrece_editar_y_quitar_por_post(cliente_admin):
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert 'href="/admin/funciones/3">Editar</a>' in html
    assert '<form method="post" action="/admin/funciones/3/baja">' in html
    assert html.count(">Quitar</button>") == 5


@pytest.mark.parametrize("metodo, ruta", RUTAS[1:])
def test_acciones_de_funciones_avisan_pendiente_y_vuelven_al_listado(cliente_admin, metodo, ruta):
    respuesta = getattr(cliente_admin, metodo)(ruta, data={"pelicula_id": "1", "precio": "5500"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin/funciones"
    html = cliente_admin.get("/admin/funciones").get_data(as_text=True)
    assert "falta conectar el backend" in html
