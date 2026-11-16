"""Páginas para el cliente: cartelera, compra y perfil."""
from datetime import date, datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.frontend.api_client import llamar
from src.frontend.filtros import hora
from src.frontend.sesion import ir_al_login, requiere_sesion
from src.frontend.validaciones import (
    MAXIMO_CANTIDAD_SERVICIO,
    leer_formulario,
    validar_cantidades_servicios,
    validar_login,
    validar_pago,
    validar_registro,
)

publico_bp = Blueprint("publico", __name__)

OPCION_TODOS_LOS_LOCALES = {"valor": "", "texto": "Todos"}


def _opciones_locales():
    """Locales de GET /api/locales como opciones {"valor", "texto"} para el header y los filtros (SCRUM-126).

    Si el backend falla o responde algo inesperado, la lista queda vacía: el filtro solo ofrece "Todos" y la página
    se muestra igual.
    """
    datos, error = llamar("GET", "/api/locales")
    if error or not isinstance(datos, list):
        return []
    return [
        {"valor": str(local["id"]), "texto": str(local.get("nombre") or f"Local {local['id']}")}
        for local in datos
        if isinstance(local, dict) and local.get("id") is not None
    ]


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


def _cartelera(local_id="", fecha=""):
    """Películas en cartel (GET /api/cartelera) con los filtros que vengan. Devuelve (peliculas, error)."""
    params = {nombre: valor for nombre, valor in (("local_id", local_id), ("fecha", fecha)) if valor}
    datos, error = llamar("GET", "/api/cartelera", params=params or None)
    peliculas = None if error else _solo_peliculas(datos)
    if error is None and peliculas is None:
        error = {"mensaje": "No pudimos leer la cartelera. Probá de nuevo en unos minutos."}
    return (peliculas, None) if error is None else ([], error)


def _contexto_header(local_id=""):
    """Locales y películas para los selectores del header en las pantallas que no arman la cartelera.

    Las películas son las que están en cartel en el local elegido. Si algo falla, ese selector queda deshabilitado
    (el header no avisa: la pantalla tiene su propio contenido).
    """
    peliculas, _ = _cartelera(local_id)
    return {"header_locales": _opciones_locales(), "header_peliculas": _header_peliculas(peliculas)}


# Elegir una película en el header lleva a su detalle (con el local y la fecha elegidos), así la selección cambia lo
# que se ve desde cualquier pantalla. Sin película, la cartelera se filtra por local y fecha en el backend.
@publico_bp.get("/")
def inicio():
    local_id = (request.args.get("local_id") or "").strip()
    fecha = (request.args.get("fecha") or "").strip()
    pelicula_id = _id_pelicula(request.args.get("pelicula_id"))
    if pelicula_id is not None:
        return redirect(url_for("publico.detalle_pelicula", id=pelicula_id, local_id=local_id or None,
                                fecha=fecha or None))
    peliculas, error = _cartelera(local_id, fecha)
    locales = _opciones_locales()
    if error:
        flash(error["mensaje"], "error")
    return render_template(
        "inicio.html",
        peliculas=peliculas,
        locales=[OPCION_TODOS_LOS_LOCALES, *locales],
        local_id=local_id,
        fecha=fecha,
        error_cartelera=error is not None,
        header_locales=locales,
        header_peliculas=_header_peliculas(peliculas),
    )


MENSAJE_LOCAL_INVALIDO = "No reconocemos ese local. Te mostramos las funciones de todos los locales."
MENSAJE_FECHA_INVALIDA = "La fecha no es válida (usá el formato AAAA-MM-DD). Te mostramos las funciones de todos los días."


def _filtros_detalle(args, locales):
    """Valida local_id (contra las opciones de locales) y fecha del GET.

    Devuelve (local, fecha, errores): lo inválido queda vacío y con su mensaje.
    """
    ids_locales = {local["valor"] for local in locales}
    local_id = (args.get("local_id") or "").strip()
    fecha = (args.get("fecha") or "").strip()
    errores = {}
    if local_id and local_id not in ids_locales:
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


def _funciones_filtradas(funciones, local_id, fecha):
    funciones = [funcion for funcion in funciones if isinstance(funcion, dict)]
    if local_id:
        funciones = [funcion for funcion in funciones if str(funcion.get("local_id")) == local_id]
    if fecha:
        funciones = [funcion for funcion in funciones if str(funcion.get("fecha_hora") or "")[:10] == fecha]
    return sorted(funciones, key=lambda funcion: (str(funcion.get("nombre_local") or ""), str(funcion.get("fecha_hora") or "")))


def _peliculas_del_header_en_detalle(pelicula, local_id):
    """Las películas en cartel del local elegido, para poder cambiar de película desde el detalle. La que se está
    viendo siempre está (aunque no tenga funciones en ese local), así el selector la muestra elegida."""
    peliculas, _ = _cartelera(local_id)
    if all(otra["id"] != pelicula["id"] for otra in peliculas):
        peliculas = [pelicula, *peliculas]
    return _header_peliculas(peliculas)


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
    locales = _opciones_locales()
    local_id, fecha, errores_filtro = _filtros_detalle(request.args, locales)
    funciones = pelicula.get("funciones") if isinstance(pelicula.get("funciones"), list) else []
    filtradas = _funciones_filtradas(funciones, local_id, fecha)
    return render_template(
        "pelicula.html",
        pelicula={**pelicula, "funciones": filtradas},
        locales=[OPCION_TODOS_LOS_LOCALES, *locales],
        local_id=local_id,
        fecha=fecha,
        errores_filtro=errores_filtro,
        filtro_activo=bool(local_id or fecha),
        total_funciones=len([funcion for funcion in funciones if isinstance(funcion, dict)]),
        header_locales=locales,
        header_peliculas=_peliculas_del_header_en_detalle(pelicula, local_id),
        pelicula_id=str(pelicula["id"]),
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
    # siguiente es la página que pidió el login (la guarda sesion.ir_al_login): se vuelve ahí en vez de al inicio.
    siguiente = session.get("siguiente")
    session.clear()
    session.update(token=usuario["token"], rol=usuario["rol"], nombre=usuario["nombre"])
    flash(f"¡Hola, {usuario['nombre']}!", "exito")
    return redirect(siguiente) if siguiente else _ir_al_inicio(usuario["rol"])


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


MAXIMO_DIGITOS_ID = 18  # int() falla con textos larguísimos; ningún id real se acerca a este largo


def _ids_butacas(valores):
    # isdecimal() y no isdigit(): "²" es dígito pero int("²") falla y la página daría error 500.
    return [int(valor) for valor in valores if valor.isdecimal() and len(valor) <= MAXIMO_DIGITOS_ID and int(valor) > 0]


def _mensaje_conflicto(seleccionadas, butacas_mapa, mensaje_api):
    """Nombra las butacas elegidas que se ocuparon, según el mapa recién pedido: el 409 del backend no siempre las dice."""
    tomadas = [f"{butaca['fila']}{butaca['numero']}" for butaca in butacas_mapa
               if butaca["id"] in seleccionadas and butaca["estado"] != "libre"]
    return f"Estas butacas ya no están disponibles: {', '.join(tomadas)}. Elegí otras." if tomadas else mensaje_api


@publico_bp.get("/servicios")
def servicios():
    """Servicios activos (menú del header). Es público: se pueden ver antes de comprar."""
    lista, error = llamar("GET", "/api/servicios")
    if error is None and not isinstance(lista, list):
        error = {"mensaje": "No pudimos leer los servicios. Probá de nuevo en unos minutos."}
    if error:
        flash(error["mensaje"], "error")
    lista = [] if error else [servicio for servicio in lista if isinstance(servicio, dict) and "id" in servicio]
    return render_template("servicios.html", servicios=lista, sin_datos=error is not None, **_contexto_header())


@publico_bp.get("/mis-compras")
@requiere_sesion
def mis_compras():
    """Menú "Mis compras" del header: las compras están en el perfil, con sus pestañas."""
    return redirect(url_for("publico.perfil") + "#titulo-compras")


# Ver el mapa de butacas es público (GET); reservar (POST) pide sesión. Por eso el chequeo va acá y no con
# @requiere_sesion, que protegería los dos métodos. Las butacas elegidas viajan en la URL para que, al volver del
# login, sigan marcadas (la grilla solo marca las que continúan libres).
@publico_bp.route("/funciones/<int:funcion_id>/butacas", methods=["GET", "POST"])
def butacas(funcion_id):
    seleccionadas = _ids_butacas(request.args.getlist("butaca_ids"))
    error_formulario = ""
    estado = 200
    hay_conflicto = False
    if request.method == "POST":
        valores = request.form.getlist("butaca_ids")
        seleccionadas = _ids_butacas(valores)
        if not session.get("token"):
            destino = url_for("publico.butacas", funcion_id=funcion_id, butaca_ids=seleccionadas)
            return ir_al_login("Ingresá para reservar tus butacas.", volver_a=destino)
        if not valores or len(seleccionadas) != len(valores):
            error_formulario = "Elegí al menos una butaca libre."
            estado = 400
        else:
            compra, error = llamar("POST", "/api/compras", json={"funcion_id": funcion_id, "butaca_ids": seleccionadas})
            if error is None:
                session["compra_id"] = compra["id"]
                flash(f"Reservamos tus butacas hasta las {hora(compra['vence_en'])}.", "exito")
                return redirect(url_for("publico.servicios_compra", compra_id=compra["id"]))
            error_formulario = error["mensaje"]
            estado = error["status"]
            hay_conflicto = error["codigo"] == "BUTACA_OCUPADA"
    funcion, error = llamar("GET", f"/api/funciones/{funcion_id}")
    mapa, error_mapa = (None, error) if error else llamar("GET", f"/api/funciones/{funcion_id}/butacas")
    if error_mapa:
        flash(error_mapa["mensaje"], "error")
        return redirect(url_for("publico.inicio"))
    if hay_conflicto:
        error_formulario = _mensaje_conflicto(seleccionadas, mapa["butacas"], error_formulario)
    return render_template(
        "compra/butacas.html", funcion=funcion, mapa=mapa, seleccionadas=seleccionadas, error=error_formulario,
    ), estado


# Pago y compra confirmada (SCRUM-68). Las dos pantallas muestran el detalle real de GET /api/compras/<id> y el pago
# confirma con POST /api/compras/<id>/confirmar: el total y el QR son los del backend. Los datos de la tarjeta solo se
# validan acá y no viajan al backend, porque el pago es simulado.
CAMPOS_PAGO = ("titular", "numero", "vencimiento", "codigo_seguridad", "acepto")
MENSAJE_RESERVA_INACTIVA = "Esta reserva ya no está activa. Elegí tus butacas de nuevo."
# Rechazos del backend que no se arreglan reintentando el pago: se vuelve al inicio en vez de al formulario.
ERRORES_SIN_REINTENTO = ("COMPRA_NO_PENDIENTE", "RESERVA_VENCIDA", "NO_ENCONTRADO", "SIN_PERMISO")

def _reserva_vigente(compra):
    # El backend marca "vencida" recién al reservar de nuevo o al confirmar: una pendiente puede tener el plazo ya pasado.
    return compra["estado"] == "pendiente" and datetime.fromisoformat(compra["vence_en"]) > datetime.now()


def _compra_pendiente(compra_id):
    """Detalle de la compra, o None con un aviso si no existe, es ajena o la reserva ya no está activa."""
    compra, error = llamar("GET", f"/api/compras/{compra_id}")
    if error is None and not _reserva_vigente(compra):
        error = {"mensaje": MENSAJE_RESERVA_INACTIVA}
    if error is not None:
        flash(error["mensaje"], "error")
        return None
    return compra


def _servicios_activos():
    """Si la lista no se puede cargar, se avisa y la página sigue: se puede continuar sin servicios."""
    servicios, error = llamar("GET", "/api/servicios")
    if error is not None:
        flash(error["mensaje"], "error")
        return []
    return servicios


def _cantidades_del_formulario(servicios, accion):
    """{servicio_id: texto}, solo de los servicios que se muestran: otro campo que llegue en el POST se ignora."""
    if accion == "sin_servicios":
        return {servicio["id"]: "0" for servicio in servicios}
    return {servicio["id"]: request.form.get(f"cantidad_{servicio['id']}", "").strip() or "0" for servicio in servicios}


# Paso opcional entre butacas y pago (SCRUM-65). Las cantidades se guardan con PUT /api/compras/<id>/servicios y el
# total que se muestra es siempre el del backend: el frontend no suma precios. "accion" sale del botón que se tocó:
# "actualizar" (o Enter) recalcula el total y vuelve acá; "pago" y "sin_servicios" siguen al pago.
@publico_bp.route("/compras/<int:compra_id>/servicios", methods=["GET", "POST"])
@requiere_sesion
def servicios_compra(compra_id):
    compra = _compra_pendiente(compra_id)
    if compra is None:
        return redirect(url_for("publico.inicio"))
    servicios = _servicios_activos()
    elegidas = {servicio["servicio_id"]: str(servicio["cantidad"]) for servicio in compra["servicios"]}
    cantidades = {servicio["id"]: elegidas.get(servicio["id"], "0") for servicio in servicios}
    errores, error_api, estado = {}, "", 200
    if request.method == "POST":
        accion = request.form.get("accion")
        cantidades = _cantidades_del_formulario(servicios, accion)
        errores = validar_cantidades_servicios(cantidades)
        if errores:
            estado = 400
        else:
            pedido = [{"servicio_id": servicio_id, "cantidad": int(texto)}
                      for servicio_id, texto in cantidades.items() if int(texto) > 0]
            _, error = llamar("PUT", f"/api/compras/{compra_id}/servicios", json=pedido)
            if error is None and accion in ("pago", "sin_servicios"):
                return redirect(url_for("publico.pago", compra_id=compra_id))
            if error is None:
                flash("Actualizamos el total de tu compra.", "exito")
                return redirect(url_for("publico.servicios_compra", compra_id=compra_id))
            if error["status"] != 400:  # la compra ya no se puede modificar (vencida, pagada o ajena)
                flash(error["mensaje"], "error")
                return redirect(url_for("publico.inicio"))
            error_api, estado = error["mensaje"], 400
    pagina = render_template("compra/servicios.html", compra=compra, servicios=servicios, cantidades=cantidades,
                             errores=errores, error=error_api, maximo_cantidad=MAXIMO_CANTIDAD_SERVICIO)
    return pagina, estado


def _ya_confirmada(compra_id, error):
    if error["codigo"] != "COMPRA_NO_PENDIENTE":
        return False
    compra, error_detalle = llamar("GET", f"/api/compras/{compra_id}")
    return error_detalle is None and compra["estado"] == "confirmada"


def _confirmar_pago(compra_id):
    resultado, error = llamar("POST", f"/api/compras/{compra_id}/confirmar")
    destino = url_for("publico.compra_confirmada", compra_id=compra_id)
    if error is None:
        if resultado["email_enviado"]:
            session.pop("email_fallido", None)
        else:
            session["email_fallido"] = compra_id
    elif not _ya_confirmada(compra_id, error):
        flash(error["mensaje"], "error")
        sin_reintento = error["codigo"] in ERRORES_SIN_REINTENTO
        destino = url_for("publico.inicio") if sin_reintento else url_for("publico.pago", compra_id=compra_id)
    return redirect(destino)


@publico_bp.route("/compras/<int:compra_id>/pago", methods=["GET", "POST"])
@requiere_sesion
def pago(compra_id):
    compra, error = llamar("GET", f"/api/compras/{compra_id}")
    if error is not None:
        flash(error["mensaje"], "error")
        return redirect(url_for("publico.inicio"))
    if compra["estado"] == "confirmada":  # volver atrás o repetir el envío no vuelve a cobrar
        return redirect(url_for("publico.compra_confirmada", compra_id=compra_id))
    if not _reserva_vigente(compra):
        flash(MENSAJE_RESERVA_INACTIVA, "error")
        return redirect(url_for("publico.inicio"))
    formulario = leer_formulario(request.form, *CAMPOS_PAGO)
    errores = validar_pago(formulario) if request.method == "POST" else {}
    if request.method == "POST" and not errores:
        return _confirmar_pago(compra_id)
    # Los datos sensibles de la tarjeta no se devuelven a la página, como la contraseña en el login.
    formulario.update(numero="", codigo_seguridad="")
    pagina = render_template("compra/pago.html", compra=compra, formulario=formulario, errores=errores)
    return pagina, 400 if errores else 200


@publico_bp.get("/compras/<int:compra_id>/confirmada")
@requiere_sesion
def compra_confirmada(compra_id):
    compra, error = llamar("GET", f"/api/compras/{compra_id}")
    if error is not None:
        flash(error["mensaje"], "error")
        return redirect(url_for("publico.inicio"))
    if compra["estado"] != "confirmada":
        pendiente = _reserva_vigente(compra)
        flash("Completá el pago para confirmar tu compra." if pendiente else "Esta compra no está confirmada.", "error")
        destino = url_for("publico.pago", compra_id=compra_id) if pendiente else url_for("publico.inicio")
        return redirect(destino)
    email_enviado = session.get("email_fallido") != compra_id
    return render_template("compra/confirmada.html", compra=compra, email_enviado=email_enviado)

# Cancelación desde el perfil (con sesión) o desde el enlace firmado del email (sin sesión, SCRUM-70).
# Abrir el enlace con GET solo muestra el resumen y el botón de confirmación; la cancelación ocurre solo con POST.
@publico_bp.route("/compras/<int:compra_id>/cancelar", methods=["GET", "POST"])
@requiere_sesion
def cancelar_compra(compra_id):
    volver_url = url_for("publico.perfil")
    accion_url = url_for("publico.cancelar_compra", compra_id=compra_id)
    if request.method == "POST":
        _, error = llamar("POST", f"/api/compras/{compra_id}/cancelar")
        if error is None:
            flash(f"Cancelaste la compra #{compra_id}. Liberamos las butacas y el QR ya no es válido.", "exito")
            return redirect(volver_url)
        flash(error["mensaje"], "error")
        compra, error_detalle = llamar("GET", f"/api/compras/{compra_id}")
        if error_detalle is not None:
            return redirect(volver_url)
        return (
            render_template(
                "compra/cancelar.html",
                compra=compra,
                accion_url=accion_url,
                volver_url=volver_url,
                motivo_rechazo=error["mensaje"],
            ),
            error["status"],
        )

    compra, error = llamar("GET", f"/api/compras/{compra_id}")
    if error is not None:
        flash(error["mensaje"], "error")
        return redirect(volver_url)
    return render_template("compra/cancelar.html", compra=compra, accion_url=accion_url, volver_url=volver_url)


@publico_bp.route("/cancelar/<token>", methods=["GET", "POST"])
def cancelar_por_token(token):
    volver_url = url_for("publico.inicio")
    accion_url = url_for("publico.cancelar_por_token", token=token)
    if request.method == "POST":
        resultado, error = llamar("POST", "/api/compras/cancelar-por-token", json={"token": token})
        if error is None:
            compra, _ = llamar("GET", "/api/compras/por-token", params={"token": token})
            flash(f"Cancelaste la compra #{resultado['id']}. Liberamos las butacas y el QR ya no es válido.", "exito")
            return render_template(
                "compra/cancelar.html", compra=compra, cancelada_exito=True, volver_url=volver_url
            )
        if error["codigo"] == "TOKEN_INVALIDO":
            return (
                render_template(
                    "compra/cancelar.html", compra=None, error_enlace=error["mensaje"], volver_url=volver_url
                ),
                error["status"],
            )
        compra, error_detalle = llamar("GET", "/api/compras/por-token", params={"token": token})
        if error_detalle is not None:
            return (
                render_template(
                    "compra/cancelar.html", compra=None, error_enlace=error_detalle["mensaje"], volver_url=volver_url
                ),
                error_detalle["status"],
            )
        return (
            render_template(
                "compra/cancelar.html",
                compra=compra,
                accion_url=accion_url,
                volver_url=volver_url,
                motivo_rechazo=error["mensaje"],
            ),
            error["status"],
        )

    compra, error = llamar("GET", "/api/compras/por-token", params={"token": token})
    if error is not None:
        return (
            render_template("compra/cancelar.html", compra=None, error_enlace=error["mensaje"], volver_url=volver_url),
            error["status"],
        )
    return render_template("compra/cancelar.html", compra=compra, accion_url=accion_url, volver_url=volver_url)


# Perfil del cliente (SCRUM-50 sobre la maqueta de SCRUM-116): cuenta, compras por pestaña y películas vistas.
# Los tres datos salen del backend (GET /api/auth/me, /api/me/compras y /api/me/peliculas-vistas); el backend ya
# dice si cada compra es cancelable y hasta cuándo, así la regla del plazo vive en un solo lugar.
PESTANAS_PERFIL = (("proximas", "Próximas"), ("historial", "Historial"), ("canceladas", "Canceladas"))
RUTAS_PERFIL = (
    ("usuario", "/api/auth/me"), ("compras", "/api/me/compras"), ("peliculas_vistas", "/api/me/peliculas-vistas"),
)


def _datos_perfil():
    """Pide al backend los datos del perfil. Devuelve (datos, error) con el primer error que aparezca."""
    datos = {}
    for clave, ruta in RUTAS_PERFIL:
        respuesta, error = llamar("GET", ruta)
        if error:
            return None, error
        datos[clave] = respuesta
    return datos, None


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
    if compra.get("estado") == "cancelada":
        return "canceladas"
    fecha = _fecha_funcion((compra.get("funcion") or {}).get("fecha_hora"))
    if compra.get("utilizada_en") or fecha is None or fecha < ahora.replace(microsecond=0):
        return "historial"
    return "proximas"


@publico_bp.get("/perfil")
@requiere_sesion
def perfil():
    claves = [clave for clave, _ in PESTANAS_PERFIL]
    # Una pestaña que no existe (?estado=cualquiera) muestra las próximas en lugar de romper la página.
    pestana = request.args.get("estado") if request.args.get("estado") in claves else claves[0]
    datos, error = _datos_perfil()
    if error:
        flash(error["mensaje"], "error")
        datos = {"usuario": {"nombre": session.get("nombre") or "Mi perfil"}, "compras": [], "peliculas_vistas": []}
    ahora = datetime.now()
    compras = [compra for compra in datos["compras"] or [] if _pestana_compra(compra, ahora) == pestana]
    return render_template(
        "perfil.html", usuario=datos["usuario"] or {}, compras=compras,
        peliculas_vistas=datos["peliculas_vistas"] or [],
        pestanas=PESTANAS_PERFIL, pestana=pestana, horas_limite=current_app.config["HORAS_LIMITE_CANCELACION"],
        sin_datos=error is not None,
    )
