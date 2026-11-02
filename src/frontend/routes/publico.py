"""Páginas para el cliente: cartelera, compra y perfil."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from src.frontend.api_client import llamar
from src.frontend.sesion import ir_al_login, requiere_sesion
from src.frontend.validaciones import leer_formulario, validar_login, validar_pago, validar_registro

publico_bp = Blueprint("publico", __name__)


@publico_bp.get("/")
def inicio():
    datos, error = llamar("GET", "/api/salud")
    estado_api = error["mensaje"] if error else datos.get("estado")
    return render_template("inicio.html", estado_api=estado_api)


# Ingresar y crear cuenta (SCRUM-88, SCRUM-46). El formulario se valida acá y después en el backend; si hay errores
# se vuelve a mostrar con los datos cargados (sin la contraseña). Al entrar, la sesión guarda token, rol y nombre.
def _iniciar_sesion(formulario):
    return llamar("POST", "/api/auth/login", json={"email": formulario["email"], "password": formulario["password"]})


def _registrar_e_iniciar_sesion(formulario):
    cuenta = {campo: formulario[campo] for campo in ("nombre", "email", "password")}
    _, error = llamar("POST", "/api/auth/registro", json=cuenta)
    return (None, error) if error else _iniciar_sesion(formulario)


def _abrir_sesion(usuario):
    session.clear()
    session.update(token=usuario["token"], rol=usuario["rol"], nombre=usuario["nombre"])
    flash(f"¡Hola, {usuario['nombre']}!", "exito")
    return _ir_al_inicio(usuario["rol"])


def _ir_al_inicio(rol):
    return redirect(url_for("backoffice.inicio") if rol == "admin" else url_for("publico.inicio"))


def _pantalla_cuenta(template, campos, validar, enviar):
    # Con la sesión abierta no tiene sentido volver a ingresar o crear otra cuenta: primero hay que salir.
    if session.get("token"):
        flash("Ya iniciaste sesión. Para usar otra cuenta, primero salí.", "error")
        return _ir_al_inicio(session.get("rol"))
    formulario = leer_formulario(request.form, *campos)
    if request.method == "GET":
        return render_template(template, formulario=formulario, errores={})
    errores = validar(formulario)
    if errores:
        return render_template(template, formulario=formulario, errores=errores), 400
    usuario, error = enviar(formulario)
    if error is None:
        return _abrir_sesion(usuario)
    flash(error["mensaje"], "error")
    return render_template(template, formulario=formulario, errores={}), error["status"]


@publico_bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    return _pantalla_cuenta("auth/login.html", ("email", "password"), validar_login, _iniciar_sesion)


@publico_bp.route("/registro", methods=["GET", "POST"])
def registro():
    return _pantalla_cuenta(
        "auth/registro.html", ("nombre", "email", "password", "repetir_password"), validar_registro,
        _registrar_e_iniciar_sesion,
    )


@publico_bp.post("/salir")
def salir():
    session.clear()
    flash("Cerraste la sesión.", "exito")
    return redirect(url_for("publico.inicio"))


# Ver el mapa de butacas es público (GET); reservar (POST) pide sesión. Por eso el chequeo va acá y no con
# @requiere_sesion, que protegería los dos métodos.
@publico_bp.route("/funciones/<int:funcion_id>/butacas", methods=["GET", "POST"])
def butacas(funcion_id):
    seleccionadas = []
    error_formulario = ""
    datos_invalidos = False
    if request.method == "POST":
        if not session.get("token"):
            return ir_al_login("Ingresá para reservar tus butacas.")
        valores = request.form.getlist("butaca_ids")
        seleccionadas = [int(valor) for valor in valores if valor.isdigit() and int(valor) > 0]
        if not valores or len(seleccionadas) != len(valores):
            error_formulario = "Elegí al menos una butaca libre."
            datos_invalidos = True
        else:
            compra, error = llamar("POST", "/api/compras", json={"funcion_id": funcion_id, "butaca_ids": seleccionadas})
            if error is None:
                flash("Reservamos tus butacas por 10 minutos.", "exito")
                return redirect(url_for("publico.pago", compra_id=compra["id"]))
            error_formulario = error["mensaje"]
    funcion, error = llamar("GET", f"/api/funciones/{funcion_id}")
    mapa, error_mapa = (None, error) if error else llamar("GET", f"/api/funciones/{funcion_id}/butacas")
    if error_mapa:
        flash(error_mapa["mensaje"], "error")
        return redirect(url_for("publico.inicio"))
    return render_template(
        "compra/butacas.html", funcion=funcion, mapa=mapa, seleccionadas=seleccionadas, error=error_formulario,
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
        "email": "lucas@email.com", "qr_png_base64": QR_EJEMPLO if confirmada else None, "cancelable": confirmada,
    }

def _servicios_ejemplo():
    return [
        {
            "id": 1,
            "nombre": "Combo pochoclos grande",
            "descripcion": "Pochoclos grandes y gaseosa de 500ml",
            "precio": 6500
        },
        {
            "id": 2,
            "nombre": "Gaseosa",
            "descripcion": "Gaseosa de 500ml",
            "precio": 2500
        },
        {
            "id": 3,
            "nombre": "Estacionamiento",
            "descripcion": "Estacionamiento durante la función",
            "precio": 3000
        },
        {
            "id": 4,
            "nombre": "Acceso VIP",
            "descripcion": "Butaca reclinable y servicio en sala",
            "precio": 8000
        }
    ]

@publico_bp.get("/compras/<int:compra_id>/servicios")
@requiere_sesion
def servicios_compra(compra_id):
    compra = _compra_ejemplo(compra_id)
    servicios = _servicios_ejemplo()

    return render_template(
        "compra/servicios.html",
        compra=compra,
        servicios=servicios
    )

@publico_bp.route("/compras/<int:compra_id>/pago", methods=["GET", "POST"])
@requiere_sesion
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
@requiere_sesion
def compra_confirmada(compra_id):
    return render_template("compra/confirmada.html", compra=_compra_ejemplo(compra_id, confirmada=True))


# Cancelación maquetada (SCRUM-115) con la compra confirmada de ejemplo. SCRUM-70 reemplaza _compra_ejemplo por
# llamar("GET", f"/api/compras/{compra_id}") y el POST por /api/compras/<id>/cancelar (errores 409 con flash).
@publico_bp.route("/compras/<int:compra_id>/cancelar", methods=["GET", "POST"])
@requiere_sesion
def cancelar_compra(compra_id):
    if request.method == "POST":
        flash(f"Cancelaste la compra #{compra_id}. Liberamos las butacas y el QR ya no es válido.", "exito")
        return redirect(url_for("publico.inicio"))
    return render_template("compra/cancelar.html", compra=_compra_ejemplo(compra_id, confirmada=True))
