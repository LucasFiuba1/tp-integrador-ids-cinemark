"""Páginas para el cliente: cartelera, compra y perfil."""
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from src.frontend.api_client import llamar
from src.frontend.ejemplos import servicios_ejemplo
from src.frontend.filtros import hora
from src.frontend.sesion import ir_al_login, requiere_sesion
from src.frontend.validaciones import leer_formulario, validar_login, validar_pago, validar_registro

publico_bp = Blueprint("publico", __name__)

# El desplegable usa los locales del seed: GET /api/locales todavía no está en el backend.
LOCALES_CARTELERA = (
    {"valor": "", "texto": "Todos"},
    {"valor": "1", "texto": "Paradiso Centro"},
    {"valor": "2", "texto": "Paradiso Belgrano"},
    {"valor": "3", "texto": "Paradiso Palermo"},
)


def _header_locales():
    # El header ya trae su opción "Elegí local": acá van solo los locales reales.
    return [local for local in LOCALES_CARTELERA if local["valor"]]


def _nombres_locales():
    return {local["valor"]: local["texto"] for local in _header_locales()}


def _header_peliculas(peliculas):
    return [
        {"valor": str(pelicula["id"]), "texto": str(pelicula.get("titulo") or f"Película {pelicula['id']}")}
        for pelicula in peliculas
    ]


def _solo_peliculas(datos):
    """Deja las películas con forma de dict e id; ignora cualquier otro dato inesperado del backend."""
    if not isinstance(datos, list):
        return None
    return [pelicula for pelicula in datos if isinstance(pelicula, dict) and pelicula.get("id") is not None]


def _id_pelicula(texto):
    # isdecimal() y no isdigit(): "²" es dígito pero int("²") falla.
    texto = (texto or "").strip()
    return int(texto) if texto.isdecimal() and int(texto) > 0 else None


@publico_bp.get("/")
def inicio():
    local_id = (request.args.get("local_id") or "").strip()
    fecha = (request.args.get("fecha") or "").strip()
    pelicula_id = _id_pelicula(request.args.get("pelicula_id"))
    params = {nombre: valor for nombre, valor in (("local_id", local_id), ("fecha", fecha)) if valor}
    datos, error = llamar("GET", "/api/cartelera", params=params or None)
    peliculas = [] if error else _solo_peliculas(datos)
    error_cartelera = bool(error) or peliculas is None
    if error_cartelera:
        flash(error["mensaje"] if error else "No pudimos leer la cartelera. Probá de nuevo en unos minutos.", "error")
        peliculas = []
    # La cartelera del backend no filtra por película: el catálogo del header sale de la respuesta completa.
    header_peliculas = _header_peliculas(peliculas)
    if pelicula_id is not None:
        peliculas = [pelicula for pelicula in peliculas if pelicula["id"] == pelicula_id]
    return render_template(
        "inicio.html",
        peliculas=peliculas,
        locales=LOCALES_CARTELERA,
        local_id=local_id,
        fecha=fecha,
        pelicula_id=str(pelicula_id) if pelicula_id is not None else "",
        error_cartelera=error_cartelera,
        header_locales=_header_locales(),
        header_peliculas=header_peliculas,
    )


MENSAJE_LOCAL_INVALIDO = "No reconocemos ese local. Te mostramos las funciones de todos los locales."
MENSAJE_FECHA_INVALIDA = "La fecha no es válida (usá el formato AAAA-MM-DD). Te mostramos las funciones de todos los días."


def _filtros_detalle(args):
    """Valida local_id y fecha del GET. Devuelve (local, fecha, errores): lo inválido queda vacío y con su mensaje."""
    locales = _nombres_locales()
    local_id = (args.get("local_id") or "").strip()
    fecha = (args.get("fecha") or "").strip()
    errores = {}
    if local_id and local_id not in locales:
        errores["local_id"] = MENSAJE_LOCAL_INVALIDO
        local_id = ""
    if fecha:
        try:
            valida = date.fromisoformat(fecha).isoformat() == fecha
        except ValueError:
            valida = False
        if not valida:
            errores["fecha"] = MENSAJE_FECHA_INVALIDA
            fecha = ""
    return local_id, fecha, errores


def _funciones_filtradas(funciones, nombre_local, fecha):
    # GET /api/peliculas/<id> no trae local_id de cada función: se filtra por nombre del local (seed).
    funciones = [funcion for funcion in funciones if isinstance(funcion, dict)]
    if nombre_local:
        funciones = [funcion for funcion in funciones if funcion.get("nombre_local") == nombre_local]
    if fecha:
        funciones = [funcion for funcion in funciones if str(funcion.get("fecha_hora") or "")[:10] == fecha]
    return sorted(funciones, key=lambda funcion: (str(funcion.get("nombre_local") or ""), str(funcion.get("fecha_hora") or "")))


@publico_bp.get("/peliculas/<int:id>")
def detalle_pelicula(id):
    pelicula, error = llamar("GET", f"/api/peliculas/{id}")
    if error is None and not isinstance(pelicula, dict):
        error = {"status": 502, "codigo": "RESPUESTA_INVALIDA", "mensaje": "No pudimos leer la película. Probá de nuevo."}
    if error:
        if error["status"] == 404:
            return render_template("errores/404.html"), 404
        flash(error["mensaje"], "error")
        return redirect(url_for("publico.inicio"))
    local_id, fecha, errores_filtro = _filtros_detalle(request.args)
    funciones = pelicula.get("funciones") if isinstance(pelicula.get("funciones"), list) else []
    filtradas = _funciones_filtradas(funciones, _nombres_locales().get(local_id), fecha)
    return render_template(
        "pelicula.html",
        pelicula={**pelicula, "funciones": filtradas},
        locales=LOCALES_CARTELERA,
        local_id=local_id,
        fecha=fecha,
        errores_filtro=errores_filtro,
        filtro_activo=bool(local_id or fecha),
        total_funciones=len([funcion for funcion in funciones if isinstance(funcion, dict)]),
        header_locales=_header_locales(),
        header_peliculas=_header_peliculas([pelicula]) if pelicula.get("id") is not None else [],
    )

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
        # isdecimal() y no isdigit(): "²" es dígito pero int("²") falla y la página daría error 500.
        seleccionadas = [int(valor) for valor in valores if valor.isdecimal() and int(valor) > 0]
        if not valores or len(seleccionadas) != len(valores):
            error_formulario = "Elegí al menos una butaca libre."
            datos_invalidos = True
        else:
            compra, error = llamar("POST", "/api/compras", json={"funcion_id": funcion_id, "butaca_ids": seleccionadas})
            if error is None:
                flash(f"Reservamos tus butacas hasta las {hora(compra['vence_en'])}.", "exito")
                return redirect(url_for("publico.servicios_compra", compra_id=compra["id"]))
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
        "pelicula": "La noche del telón",
        "poster_url": None, "local": "Paradiso Centro", "sala": "Sala 1",
        "funcion": "2026-10-24T19:30:00", "butacas": ["D5", "D6", "D7"], "subtotal_entradas": 16500,
        "servicios": [{"nombre": "Combo pochoclos grande", "cantidad": 1, "subtotal": 6500}], "total": 23000,
        "email": "lucas@email.com", "qr_png_base64": QR_EJEMPLO if confirmada else None, "cancelable": confirmada,
    }


@publico_bp.get("/compras/<int:compra_id>/servicios")
@requiere_sesion
def servicios_compra(compra_id):
    servicios = [servicio for servicio in servicios_ejemplo() if servicio["activo"]]
    return render_template("compra/servicios.html", compra=_compra_ejemplo(compra_id), servicios=servicios)


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


# Perfil del cliente maquetado (SCRUM-116). Los datos de ejemplo tienen la forma de GET /api/auth/me,
# GET /api/me/compras y GET /api/me/peliculas-vistas (más lo que pide el mockup y la API todavía no manda: el email,
# la compra pendiente con vence_en y la duración y clasificación de las vistas). SCRUM-49 los reemplaza por llamar(...).
PESTANAS_PERFIL = (("proximas", "Próximas"), ("historial", "Historial"), ("canceladas", "Canceladas"))


def _perfil_ejemplo():
    return {
        "usuario": {"id": 7, "nombre": "Lucas Berardi", "email": "lucas@email.com", "rol": "cliente"},
        "compras": [
            {"id": 1042, "estado": "confirmada", "total": 23000.0, "utilizada_en": None,
             "funcion": {"id": 13, "pelicula_id": 5, "fecha_hora": "2026-11-20T19:30:00",
                         "pelicula": "La noche del telón",
                         "poster_url": None, "sala": "Sala 1", "local": "Paradiso Centro"},
             "butacas": ["D5", "D6", "D7"],
             "servicios": [{"nombre": "Combo pochoclos grande", "cantidad": 1, "precio_unitario": 6500.0}],
             "cancelable": True},
            {"id": 1043, "estado": "confirmada", "total": 19000.0, "utilizada_en": None,
             "funcion": {"id": 11, "pelicula_id": 6, "fecha_hora": "2026-11-21T21:00:00",
                         "pelicula": "Código medianoche",
                         "poster_url": None, "sala": "Sala VIP", "local": "Paradiso Palermo"},
             "butacas": ["B4"], "servicios": [{"nombre": "Acceso VIP", "cantidad": 1, "precio_unitario": 8000.0}],
             "cancelable": False},
            {"id": 1044, "estado": "pendiente", "total": 6000.0, "utilizada_en": None,
             "vence_en": "2026-11-07T19:42:00",
             "funcion": {"id": 12, "pelicula_id": 1, "fecha_hora": "2026-11-23T17:00:00",
                         "pelicula": "Pequeños gigantes",
                         "poster_url": None, "sala": "Sala 2", "local": "Paradiso Belgrano"},
             "butacas": ["F7"], "servicios": [], "cancelable": False},
            {"id": 1031, "estado": "confirmada", "total": 16500.0, "utilizada_en": "2026-10-18T19:52:00",
             "funcion": {"id": 6, "pelicula_id": 3, "fecha_hora": "2026-10-18T20:00:00",
                         "pelicula": "Aventuras en el Plata",
                         "poster_url": None, "sala": "Sala 3", "local": "Paradiso Centro"},
             "butacas": ["E8", "E9"], "servicios": [], "cancelable": False},
            {"id": 1035, "estado": "cancelada", "total": 8500.0, "utilizada_en": None,
             "cancelada_en": "2026-10-20T12:10:00",
             "funcion": {"id": 9, "pelicula_id": 7, "fecha_hora": "2026-10-21T18:00:00",
                         "pelicula": "Sombras del pasado",
                         "poster_url": None, "sala": "Sala 1", "local": "Paradiso Belgrano"},
             "butacas": ["C7"], "servicios": [], "cancelable": False},
        ],
        "peliculas_vistas": [
            {"pelicula_id": 3, "titulo": "Aventuras en el Plata", "poster_url": None, "duracion_min": 102,
             "clasificacion": "ATP", "utilizada_en": "2026-10-18T19:52:00"},
            {"pelicula_id": 4, "titulo": "El jardín de cristal", "poster_url": None, "duracion_min": 118,
             "clasificacion": "+13", "utilizada_en": "2026-10-11T20:41:00"},
            {"pelicula_id": 1, "titulo": "Pequeños gigantes", "poster_url": None, "duracion_min": 95,
             "clasificacion": "ATP", "utilizada_en": "2026-10-04T17:02:00"},
            {"pelicula_id": 2, "titulo": "Cuando cae la lluvia", "poster_url": None, "duracion_min": 124,
             "clasificacion": "+16", "utilizada_en": "2026-09-27T21:55:00"},
        ],
    }


def _fecha_funcion(fecha_hora):
    """datetime de la función, o None si falta, no es ISO o trae zona horaria (no se puede comparar con ahora)."""
    try:
        fecha = datetime.fromisoformat(fecha_hora)
    except (TypeError, ValueError):
        return None
    return fecha if fecha.tzinfo is None else None


def _pestana_compra(compra, ahora):
    """Canceladas aparte; las usadas, las de función ya pasada o sin fecha válida van al historial y el resto son
    próximas."""
    if compra["estado"] == "cancelada":
        return "canceladas"
    fecha = _fecha_funcion(compra["funcion"].get("fecha_hora"))
    if compra.get("utilizada_en") or fecha is None or fecha < ahora.replace(microsecond=0):
        return "historial"
    return "proximas"


def _cancelable_hasta(fecha_hora, horas_limite):
    """Último momento para cancelar (datetime), o None si la fecha de la función no es válida."""
    fecha = _fecha_funcion(fecha_hora)
    return None if fecha is None else fecha - timedelta(hours=horas_limite)


def _compra_perfil(compra, ahora, horas_limite):
    # Igual que el backend: se puede cancelar una compra confirmada mientras ahora < límite.
    hasta = _cancelable_hasta(compra["funcion"].get("fecha_hora"), horas_limite)
    return dict(
        compra,
        cancelable_hasta=hasta.isoformat(timespec="seconds") if hasta else None,
        cancelable=compra["estado"] == "confirmada" and hasta is not None and ahora < hasta,
    )


@publico_bp.get("/perfil")
@requiere_sesion
def perfil():
    datos = _perfil_ejemplo()
    claves = [clave for clave, _ in PESTANAS_PERFIL]
    # Una pestaña que no existe (?estado=cualquiera) muestra las próximas en lugar de romper la página.
    pestana = request.args.get("estado") if request.args.get("estado") in claves else claves[0]
    ahora = datetime.now()
    horas_limite = current_app.config["HORAS_LIMITE_CANCELACION"]
    compras = [
        _compra_perfil(compra, ahora, horas_limite)
        for compra in datos["compras"] if _pestana_compra(compra, ahora) == pestana
    ]
    return render_template(
        "perfil.html", usuario=datos["usuario"], compras=compras, peliculas_vistas=datos["peliculas_vistas"],
        pestanas=PESTANAS_PERFIL, pestana=pestana, horas_limite=horas_limite,
    )
