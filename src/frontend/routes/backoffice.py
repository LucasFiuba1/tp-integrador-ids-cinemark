"""Páginas del administrador (ABM, dashboards y validación de QR)."""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from src.frontend.validaciones import leer_formulario, validar_codigo_qr

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

# Secciones que ya tienen su vista; el resto muestra la pantalla provisoria. Al implementar una
# (SCRUM-53, 55, 57, 72, 74, 77), agregar su endpoint acá y definir la vista con ese mismo endpoint.
SECCIONES_IMPLEMENTADAS = ("validar", "locales")

def _locales_ejemplo():
    return [
        {
            "id": 1,
            "nombre": "Paradiso Centro",
            "direccion": "Av. Corrientes 1234, CABA",
            "activa": True,
            "salas": [
                {"id": 1, "nombre": "Sala 1", "capacidad": 132, "activa": True},
                {"id": 2, "nombre": "Sala 2", "capacidad": 132, "activa": True},
            ]
        },
        {
            "id": 2,
            "nombre": "Paradiso Belgrano",
            "direccion": "Av. Cabildo 5678, CABA",
            "activa": True,
            "salas": [
                {"id": 3, "nombre": "Sala 1", "capacidad": 96, "activa": True},
                {"id": 4, "nombre": "Sala 2", "capacidad": 96, "activa": True},
            ]
        },
        {
            "id": 3,
            "nombre": "Paradiso Palermo",
            "direccion": "Av. Santa Fe 4321, CABA",
            "activa": True,
            "salas": [
                {"id": 5, "nombre": "Sala VIP", "capacidad": 36, "activa": True},
            ]
        }
    ]


def requiere_admin(vista):
    """Deja pasar solo a administradores; al resto lo manda a la cartelera con un aviso."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if session.get("rol") != "admin":
            flash("Ingresá con una cuenta de administrador para ver el backoffice.", "error")
            return redirect(url_for("publico.inicio"))
        return vista(*args, **kwargs)
    return envoltura

@backoffice_bp.get("/locales")
@requiere_admin
def locales():
    return render_template(
        "backoffice/locales.html",
        locales=_locales_ejemplo()
    )





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


# Validar ingreso maquetado (SCRUM-122) con datos de ejemplo que tienen la forma de la respuesta de
# POST /api/admin/ingresos/validar. SCRUM-74 reemplaza _resultado_ejemplo e _historial_ejemplo por llamar(...).
def _resultado_ejemplo(codigo):
    if codigo == "CP-1042-D5":
        return {
            "valido": True, "compra_id": 1042, "pelicula": "La noche del telón", "funcion": "2026-10-24T19:30:00",
            "local": "Paradiso Centro", "sala": "Sala 1", "butacas": ["D5"], "titular": "Lucas Berardi",
        }
    if codigo == "CP-1038-B3":
        return {"valido": False, "codigo": "YA_UTILIZADA", "mensaje": "Este QR ya se usó el 24/10 a las 19:10."}
    return {"valido": False, "codigo": "QR_INVALIDO", "mensaje": "El código no corresponde a ninguna entrada."}


def _historial_ejemplo():
    return [
        {"hora": "2026-10-24T19:12:00", "pelicula": "La noche del telón", "butacas": "D5", "resultado": "valida"},
        {"hora": "2026-10-24T19:10:00", "pelicula": "Código Medianoche", "butacas": "B3", "resultado": "ya_utilizada"},
        {"hora": "2026-10-24T19:04:00", "pelicula": "Pequeños gigantes", "butacas": "F7", "resultado": "valida"},
        {"hora": "2026-10-24T18:58:00", "pelicula": "La noche del telón", "butacas": "C2", "resultado": "cancelada"},
    ]


@backoffice_bp.route("/validar", methods=["GET", "POST"])
@requiere_admin
def validar():
    formulario = leer_formulario(request.form, "codigo")
    errores = validar_codigo_qr(formulario) if request.method == "POST" else {}
    resultado = _resultado_ejemplo(formulario["codigo"]) if request.method == "POST" and not errores else None
    pagina = render_template(
        "backoffice/validar.html",
        formulario=formulario, errores=errores, resultado=resultado, historial=_historial_ejemplo(),
    )
    return pagina, 400 if errores else 200


@backoffice_bp.post("/validar/confirmar")
@requiere_admin
def confirmar_ingreso():
    if request.form.get("compra_id", "").isdigit():
        flash("Ingreso confirmado: el QR quedó marcado como usado.", "exito")
    else:
        flash("No se pudo confirmar el ingreso. Volvé a validar el código.", "error")
    return redirect(url_for("backoffice.validar"))


def _pantalla_pendiente(titulo):
    def vista():
        return render_template("backoffice/pendiente.html", titulo=titulo)
    return vista


def _registrar_pendientes():
    for endpoint, titulo in SECCIONES:
        if endpoint in SECCIONES_IMPLEMENTADAS:
            continue
        backoffice_bp.add_url_rule(f"/{endpoint}", endpoint, requiere_admin(_pantalla_pendiente(titulo)))


_registrar_pendientes()
