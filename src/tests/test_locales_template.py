"""Pruebas del template maquetado del ABM de locales y salas del backoffice (SCRUM-118)."""


def test_locales_sin_sesion_redirige_al_login(cliente_frontend):
    respuesta = cliente_frontend.get("/admin/locales")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/ingresar"


def test_locales_con_admin_muestra_los_locales_y_sus_salas(cliente_admin):
    respuesta = cliente_admin.get("/admin/locales")
    html = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    for dato in ("Paradiso Centro", "Paradiso Belgrano", "Paradiso Palermo", "Sala VIP"):
        assert dato in html
