"""Páginas para el cliente: cartelera, compra y perfil."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from src.frontend.api_client import llamar
from src.frontend.validaciones import leer_formulario, validar_login, validar_pago, validar_registro

publico_bp = Blueprint("publico", __name__)


@publico_bp.get("/")
def inicio():
    try:
        estado_api = llamar("GET", "/api/salud").get("estado")
    except HTTPException as error:
        detalle = error.get_response().get_json().get("error", {})
        estado_api = detalle.get("mensaje", "No se pudo consultar la API.")
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
    try:
        if template == "auth/login.html":
            respuesta = llamar("POST", "/api/auth/login", json=formulario)
            session["token"] = respuesta["token"]
            session["rol"] = respuesta["rol"]
            session["nombre"] = respuesta["nombre"]
            flash(f"¡Hola, {respuesta['nombre']}!", "exito")
            return redirect(url_for("backoffice.inicio") if respuesta["rol"] == "admin"
                            else url_for("publico.inicio"))
        llamar("POST", "/api/auth/registro", json={
            "nombre": formulario["nombre"], "email": formulario["email"], "password": formulario["password"],
        })
        flash("Tu cuenta fue creada. Ya podés iniciar sesión.", "exito")
        return redirect(url_for("publico.ingresar"))
    except HTTPException as error:
        detalle = error.get_response().get_json().get("error", {})
        if error.code == 401 and template == "auth/login.html":
            formulario["password"] = ""
            flash(detalle.get("mensaje", "No se pudo iniciar sesión."), "error")
            return render_template(template, formulario=formulario, errores={}), 401
        if error.code == 401:
            session.clear()
            return redirect(url_for("publico.ingresar"))
        formulario["password"] = ""
        flash(detalle.get("mensaje", "No se pudo procesar la solicitud."), "error")
        return render_template(template, formulario=formulario, errores={}), error.code


@publico_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return _pantalla_cuenta("auth/login.html", ("email", "password"), validar_login)


@publico_bp.route("/registro", methods=["GET", "POST"])
def registro():
    return _pantalla_cuenta(
        "auth/registro.html", ("nombre", "email", "password", "repetir_password"), validar_registro
    )


@publico_bp.route("/funciones/<int:funcion_id>/butacas", methods=["GET", "POST"])
def butacas(funcion_id):
    seleccionadas = []
    error_formulario = ""
    datos_invalidos = False
    if request.method == "POST":
        if not session.get("token"):
            flash("Ingresá para reservar tus butacas.", "error")
            return redirect(url_for("publico.ingresar"))
        valores = request.form.getlist("butaca_ids")
        if not valores or any(not valor.isdigit() or int(valor) <= 0 for valor in valores):
            seleccionadas = [int(valor) for valor in valores if valor.isdigit() and int(valor) > 0]
            error_formulario = "Elegí al menos una butaca libre."
            datos_invalidos = True
        else:
            seleccionadas = [int(valor) for valor in valores]
            try:
                compra = llamar(
                    "POST", "/api/compras",
                    json={"funcion_id": funcion_id, "butaca_ids": seleccionadas},
                )
                flash("Reservamos tus butacas por 10 minutos.", "exito")
                return redirect(url_for("publico.pago", compra_id=compra["id"]))
            except HTTPException as error:
                detalle = error.get_response().get_json().get("error", {})
                if error.code == 401:
                    session.clear()
                    flash(detalle.get("mensaje", "Tenés que iniciar sesión."), "error")
                    return redirect(url_for("publico.ingresar"))
                error_formulario = detalle.get("mensaje", "No se pudo reservar las butacas.")
    try:
        funcion = llamar("GET", f"/api/funciones/{funcion_id}")
        mapa = llamar("GET", f"/api/funciones/{funcion_id}/butacas")
    except HTTPException as error:
        detalle = error.get_response().get_json().get("error", {})
        if error.code == 401:
            session.clear()
            flash(detalle.get("mensaje", "Tenés que iniciar sesión."), "error")
            return redirect(url_for("publico.ingresar"))
        flash(detalle.get("mensaje", "No se pudo cargar la función."), "error")
        return redirect(url_for("publico.inicio"))
    return render_template(
        "compra/butacas.html", funcion=funcion, mapa=mapa, seleccionadas=seleccionadas,
        error=error_formulario,
    ), 400 if datos_invalidos else 200


# Pago y compra confirmada maquetados (SCRUM-114) con una compra de ejemplo que tiene la forma de la respuesta de
# GET /api/compras/<id>. SCRUM-68 reemplaza _compra_ejemplo por llamar(...) y el POST por /api/compras/<id>/confirmar.
CAMPOS_PAGO = ("titular", "numero", "vencimiento", "codigo_seguridad", "acepto")
# QR de ejemplo (codifica CP-1042-D5): PNG de 23 x 23 px que la pantalla agranda sin suavizar.
QR_EJEMPLO = (
    "iVBORw0KGgoAAAANSUhEUgAAABcAAAAXAQAAAADIUekNAAAAZ0lEQVR42gFcAKP/Af8A/wMBExoCPvT4BOTwxAIARAACABQAAL76+gMh7TAA"
    "/5P+AIgE7gHTq/ACAb1EAgsTiAQDHCwCHRvoAwEynwI+3fQC5PPEAgBq9AQAzc8CHOPIAyH7vAH/AP8IeCMEJ5FRrwAAAABJRU5ErkJggg=="
)


def _compra_ejemplo(compra_id, confirmada=False):
    return {
        "id": compra_id, "estado": "confirmada" if confirmada else "pendiente", "vence_en": "2026-10-24T19:05:00",
        "pelicula": "La noche del telón", "poster_url": None, "local": "Paradiso Centro", "sala": "Sala 1",
        "funcion": "2026-10-24T19:30:00", "butacas": ["D5", "D6", "D7"], "subtotal_entradas": 16500,
        "servicios": [{"nombre": "Combo pochoclos grande", "cantidad": 1, "subtotal": 6500}], "total": 23000,
        "email": "lucas@email.com", "qr_png_base64": QR_EJEMPLO if confirmada else None,
    }


@publico_bp.route("/compras/<int:compra_id>/pago", methods=["GET", "POST"])
def pago(compra_id):
    formulario = leer_formulario(request.form, *CAMPOS_PAGO)
    errores = validar_pago(formulario) if request.method == "POST" else {}
    if request.method == "POST" and not errores:
        return redirect(url_for("publico.compra_confirmada", compra_id=compra_id))
    # Los datos sensibles de la tarjeta no se devuelven a la página, como la contraseña en el login.
    formulario.update(numero="", codigo_seguridad="")
    pagina = render_template("compra/pago.html", compra=_compra_ejemplo(compra_id), formulario=formulario,
                             errores=errores)
    return pagina, 400 if errores else 200


@publico_bp.get("/compras/<int:compra_id>/confirmada")
def compra_confirmada(compra_id):
    return render_template("compra/confirmada.html", compra=_compra_ejemplo(compra_id, confirmada=True))
