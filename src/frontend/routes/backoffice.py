"""Páginas del administrador (ABM, dashboards y validación de QR)."""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, session, url_for

backoffice_bp = Blueprint("backoffice", __name__, url_prefix="/admin")

# Ítems del sidebar: (endpoint dentro del blueprint, texto). La ruta es /admin/<endpoint>.
SECCIONES = (
    ("dashboards", "Dashboards"),
    ("peliculas", "Películas"),
    ("funciones", "Funciones"),
    ("locales", "Locales y salas"),
    ("servicios", "Servicios"),
    ("validar", "Validar ingreso"),
)

# Secciones que todavía muestran la pantalla provisoria. Al implementar una (SCRUM-53, 55, 57, 72, 74, 77),
# sacarla de acá y definir su vista con el mismo endpoint.
SECCIONES_PENDIENTES = SECCIONES


def requiere_admin(vista):
    """Deja pasar solo a administradores; al resto lo manda a la cartelera con un aviso."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if session.get("rol") != "admin":
            flash("Ingresá con una cuenta de administrador para ver el backoffice.", "error")
            return redirect(url_for("publico.inicio"))
        return vista(*args, **kwargs)
    return envoltura


@backoffice_bp.context_processor
def menu_admin():
    return {"secciones_admin": SECCIONES}


@backoffice_bp.get("/")
@requiere_admin
def inicio():
    return redirect(url_for("backoffice.dashboards"))


@backoffice_bp.post("/salir")
def salir():
    session.clear()
    flash("Cerraste la sesión.", "exito")
    return redirect(url_for("publico.inicio"))


def _pantalla_pendiente(titulo):
    def vista():
        return render_template("backoffice/pendiente.html", titulo=titulo)
    return vista


def _registrar_pendientes():
    for endpoint, titulo in SECCIONES_PENDIENTES:
        backoffice_bp.add_url_rule(f"/{endpoint}", endpoint, requiere_admin(_pantalla_pendiente(titulo)))


_registrar_pendientes()
