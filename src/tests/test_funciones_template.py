
"""Pruebas de la plantilla de programación de funciones (SCRUM-119)."""


def test_funciones_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/funciones")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_funciones_con_admin_responde_correctamente(cliente_admin):
    respuesta = cliente_admin.get("/admin/funciones")

    assert respuesta.status_code == 200


def test_funciones_muestra_las_peliculas_y_locales(cliente_admin):
    respuesta = cliente_admin.get("/admin/funciones")
    html = respuesta.get_data(as_text=True)

    datos = (
        "La noche del telón",
        "Código Medianoche",
        "Pequeños gigantes",
        "Último tren a Lisboa",
        "Paradiso Centro",
        "Paradiso Palermo",
        "Paradiso Belgrano",
        "Sala VIP",
    )

    for dato in datos:
        assert dato in html


def test_funciones_muestra_fechas_y_precios_formateados(cliente_admin):
    respuesta = cliente_admin.get("/admin/funciones")
    html = respuesta.get_data(as_text=True)

    for dato in (
        "24/10 · 19:30",
        "24/10 · 22:15",
        "28/11 · 21:00",
        "29/11 · 15:00",
        "29/11 · 20:45",
        "$5.500",
        "$9.500",
        "$6.000",
    ):
        assert dato in html
