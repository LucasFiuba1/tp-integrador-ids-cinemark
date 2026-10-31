"""Páginas para el cliente: cartelera, compra y perfil."""
from flask import Blueprint, flash, redirect, render_template, request

from src.frontend.api_client import ErrorBackend, llamar
from src.frontend.validaciones import leer_formulario, validar_login, validar_registro

publico_bp = Blueprint("publico", __name__)


@publico_bp.get("/")
def inicio():
    try:
        estado_api = llamar("GET", "/api/salud").get("estado")
    except ErrorBackend as error:
        estado_api = error.mensaje
    return render_template("inicio.html", estado_api=estado_api)


# Ingresar y crear cuenta (SCRUM-88). El formulario se valida acá y, si hay errores, se vuelve a mostrar con los
# datos cargados (sin la contraseña). SCRUM-46 reemplaza el aviso del envío válido por /api/auth/login y /registro.
def _pantalla_cuenta(template, campos, validar):
    formulario = leer_formulario(request.form, *campos)
    if request.method == "GET":
        return render_template(template, formulario=formulario, errores={})
    errores = validar(formulario)
    if errores:
        return render_template(template, formulario=formulario, errores=errores), 400
    flash("El ingreso y el registro todavía no están habilitados.", "error")
    return redirect(request.path)


@publico_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return _pantalla_cuenta("auth/login.html", ("email", "password"), validar_login)


@publico_bp.route("/registro", methods=["GET", "POST"])
def registro():
    return _pantalla_cuenta(
        "auth/registro.html", ("nombre", "email", "password", "repetir_password"), validar_registro
    )
