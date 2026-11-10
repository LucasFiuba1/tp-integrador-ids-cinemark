"""Páginas del administrador (ABM, dashboards y validación de QR)."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from src.frontend.filtros import hora
from src.frontend.sesion import requiere_admin
from src.frontend.validaciones import leer_formulario, validar_ingreso, validar_local, validar_sala, validar_servicio

from src.frontend.api_client import llamar

backoffice_bp = Blueprint("backoffice", __name__, url_prefix="/admin")

# Ítems del sidebar: (endpoint dentro del blueprint, texto). La ruta es /admin/<endpoint>.
SECCIONES = (
    ("dashboards", "Dashboards"),
    ("peliculas", "Películas"),
    ("funciones", "Funciones"),
    ("locales", "Locales y salas"),
    ("servicios", "Servicios"),
    ("ingreso", "Validar ingreso"),
)

# Secciones que ya tienen su vista; el resto muestra la pantalla provisoria. Al implementar una
# (SCRUM-53, 55, 57, 72, 74, 77), agregar su endpoint acá y definir la vista con ese mismo endpoint.
SECCIONES_IMPLEMENTADAS = ("dashboards", "peliculas", "funciones", "locales", "servicios", "ingreso")


# Programación de funciones del backoffice (SCRUM-57).

def _local_elegido(locales, local_id):
    for local in locales:
        if local["id"] == local_id:
            return local
    if locales:
        return locales[0]
    return None


def _listar_locales():
    locales, error = llamar("GET", "/api/admin/locales")

    if error is not None:
        flash(error["mensaje"], "error")
        return []

    return locales


def _listar_salas(local_id):
    salas, error = llamar("GET", "/api/admin/salas", params={"local_id": local_id},)

    if error is not None:
        flash(error["mensaje"], "error")
        return []

    return salas


def _listar_funciones(local_id=None, desde=None, hasta=None):
    params = {
        "local_id": local_id,
        "desde": desde,
        "hasta": hasta,
    }

    funciones, error = llamar("GET", "/api/admin/funciones", params=params)

    if error is not None:
        flash(error["mensaje"], "error")
        return []

    return [funcion for funcion in funciones if funcion["activa"]]


def _obtener_funcion(funcion_id):
    funciones = _listar_funciones()

    for funcion in funciones:
        if funcion["id"] == funcion_id:
            return funcion

    return None


def _opciones(registros, campo_texto):
    return [
        {"valor": registro["id"], "texto": registro[campo_texto]}
        for registro in registros
    ]

@backoffice_bp.route("/funciones", methods=["GET", "POST"])
@requiere_admin
def funciones():
    if request.method == "POST":
        pelicula_id = request.form.get("pelicula_id", type=int)
        sala_id = request.form.get("sala_id", type=int)
        fecha_hora = request.form.get("fecha_hora", "")
        precio = request.form.get("precio", type=float)

        datos = {
            "pelicula_id": pelicula_id,
            "sala_id": sala_id,
            "fecha_hora": fecha_hora + ":00",
            "precio": precio,
        }

        funcion, error = llamar("POST", "/api/admin/funciones", json=datos)

        if error is not None:
            flash(error["mensaje"], "error")
        else:
            flash("La función fue creada correctamente.", "exito")

        return redirect(url_for("backoffice.funciones"))

    local_id = request.args.get("local_id", type=int)
    fecha = request.args.get("fecha", "")

    locales = _listar_locales()
    local = _local_elegido(locales, local_id)

    if local is not None:
        local_id = local["id"]
        salas = _listar_salas(local_id)
    else:
        salas = []

    peliculas = _listar_peliculas()

    desde = None
    hasta = None

    if fecha:
        desde = fecha + "T00:00:00"
        hasta = fecha + "T23:59:59"

    funciones = _listar_funciones(local_id=local_id, desde=desde, hasta=hasta)

    formulario = {
        "pelicula_id": "",
        "local_id": local_id or "",
        "sala_id": salas[0]["id"] if salas else "",
        "fecha_hora": "",
        "precio": "",
    }

    return render_template(
        "backoffice/funciones.html",
        peliculas=_opciones(peliculas, "titulo"),
        locales=_opciones(locales, "nombre"),
        salas=_opciones(salas, "nombre"),
        formulario=formulario,
        funciones=funciones,
        fecha=fecha,
    )


@backoffice_bp.route("/funciones/<int:id>", methods=["GET", "POST"])
@requiere_admin
def editar_funcion(id):
    funcion = _obtener_funcion(id)

    if funcion is None:
        flash("La función no existe.", "error")
        return redirect(url_for("backoffice.funciones"))

    if request.method == "POST":
        pelicula_id = request.form.get("pelicula_id", type=int)
        sala_id = request.form.get("sala_id", type=int)
        fecha_hora = request.form.get("fecha_hora", "")
        precio = request.form.get("precio", type=float)

        datos = {
            "pelicula_id": pelicula_id,
            "sala_id": sala_id,
            "fecha_hora": fecha_hora + ":00",
            "precio": precio,
        }

        funcion_modificada, error = llamar("PUT", f"/api/admin/funciones/{id}", json=datos)

        if error is not None:
            flash(error["mensaje"], "error")
        else:
            flash("La función fue modificada correctamente.", "exito")

        return redirect(url_for("backoffice.funciones"))

    peliculas = _listar_peliculas()
    salas = _listar_salas(funcion["local_id"])

    formulario = {
        "pelicula_id": funcion["pelicula_id"],
        "sala_id": funcion["sala_id"],
        "fecha_hora": funcion["fecha_hora"][:16],
        "precio": funcion["precio"],
    }

    return render_template(
        "backoffice/funcion_editar.html",
        funcion=funcion,
        peliculas=_opciones(peliculas, "titulo"),
        salas=_opciones(salas, "nombre"),
        formulario=formulario,
    )


@backoffice_bp.post("/funciones/<int:id>/baja")
@requiere_admin
def baja_funcion(id):
    resultado, error = llamar("DELETE", f"/api/admin/funciones/{id}")

    if error is not None:
        flash(error["mensaje"], "error")
    else:
        flash("La función fue eliminada correctamente.", "exito")

    return redirect(url_for("backoffice.funciones"))


# ABM de locales y salas (SCRUM-55) contra /api/admin/locales y /api/admin/salas (ver docs/endpoints.md).
CAMPOS_LOCAL = ("nombre", "direccion")
CAMPOS_SALA = ("nombre", "filas", "columnas")


def _locales_con_salas():
    """Locales con sus salas activas en "salas". Si el backend falla, _listar_* ya avisaron y queda vacío."""
    locales = _listar_locales()
    salas = _listar_salas(None) if locales else []
    for local in locales:
        local["salas"] = [sala for sala in salas if sala["local_id"] == local["id"]]
    return locales


def _buscar_local(id):
    """El local con ese id, o None (con el aviso ya mostrado) si no existe o el backend falla."""
    locales, error = llamar("GET", "/api/admin/locales")
    local = None if error else next((local for local in locales if local["id"] == id), None)
    if local is None:
        flash(error["mensaje"] if error else "Ese local no existe.", "error")
    return local


def _guardar(template, campos, validar, enviar, exito, contexto):
    """Formulario de alta o edición (PRG). En POST valida, llama a enviar(formulario) -> (datos, error) y, si sale
    bien, avisa y redirige según exito(datos) -> (mensaje, url). Si no, vuelve a mostrar el formulario con los errores y el status del
    problema (400 de validación, o el 400/404/409 que devolvió la API). contexto trae el registro que se edita
    (o None) y los datos que necesita el template; en GET el formulario se llena con contexto["registro"]."""
    registro = contexto.get("registro") or {}
    if request.method == "GET":
        formulario = {campo: str(registro.get(campo, "")) for campo in campos}
        return render_template(template, formulario=formulario, errores={}, **contexto)
    formulario = leer_formulario(request.form, *campos)
    errores = validar(formulario)
    status = 400
    if not errores:
        datos, error = enviar(formulario)
        if error is None:
            mensaje, destino = exito(datos)
            flash(mensaje, "exito")
            return redirect(destino)
        flash(error["mensaje"], "error")
        status = error["status"]
    return render_template(template, formulario=formulario, errores=errores, **contexto), status


def _datos_sala(formulario):
    return {"nombre": formulario["nombre"], "filas": int(formulario["filas"]), "columnas": int(formulario["columnas"])}


def _sala_guardada(sala):
    return f"Guardaste la {sala['nombre']}: {sala['capacidad']} butacas.", url_for("backoffice.sala", id=sala["id"])


def _local_guardado(local):
    return f"Guardaste el local {local['nombre']}.", url_for("backoffice.locales")


@backoffice_bp.get("/locales")
@requiere_admin
def locales():
    return render_template("backoffice/locales.html", locales=_locales_con_salas())


@backoffice_bp.route("/locales/nuevo", methods=["GET", "POST"])
@requiere_admin
def nuevo_local():
    return _guardar(
        "backoffice/local.html", CAMPOS_LOCAL, validar_local,
        lambda formulario: llamar("POST", "/api/admin/locales", json=formulario),
        _local_guardado, {"registro": None},
    )


@backoffice_bp.route("/locales/<int:id>", methods=["GET", "POST"])
@requiere_admin
def editar_local(id):
    local = _buscar_local(id)
    if local is None:
        return redirect(url_for("backoffice.locales"))
    return _guardar(
        "backoffice/local.html", CAMPOS_LOCAL, validar_local,
        lambda formulario: llamar("PUT", f"/api/admin/locales/{id}", json=formulario),
        _local_guardado, {"registro": local},
    )


@backoffice_bp.post("/locales/<int:id>/baja")
@requiere_admin
def baja_local(id):
    _, error = llamar("DELETE", f"/api/admin/locales/{id}")
    if error:
        flash(error["mensaje"], "error")
    else:
        flash("Eliminaste el local.", "exito")
    return redirect(url_for("backoffice.locales"))


@backoffice_bp.route("/locales/<int:local_id>/salas/nueva", methods=["GET", "POST"])
@requiere_admin
def nueva_sala(local_id):
    local = _buscar_local(local_id)
    if local is None:
        return redirect(url_for("backoffice.locales"))
    return _guardar(
        "backoffice/sala.html", CAMPOS_SALA, validar_sala,
        lambda formulario: llamar("POST", "/api/admin/salas", json={"local_id": local_id, **_datos_sala(formulario)}),
        _sala_guardada, {"registro": None, "local": local},
    )


@backoffice_bp.route("/salas/<int:id>", methods=["GET", "POST"])
@requiere_admin
def sala(id):
    """Detalle de la sala con su grilla de butacas (solo lectura) y el formulario para modificarla."""
    detalle, error = llamar("GET", f"/api/admin/salas/{id}")
    if error:
        flash(error["mensaje"], "error")
        return redirect(url_for("backoffice.locales"))
    local = {"id": detalle["local_id"], "nombre": detalle["local"]}
    return _guardar(
        "backoffice/sala.html", CAMPOS_SALA, validar_sala,
        lambda formulario: llamar("PUT", f"/api/admin/salas/{id}", json=_datos_sala(formulario)),
        _sala_guardada, {"registro": detalle, "local": local},
    )


@backoffice_bp.post("/salas/<int:id>/baja")
@requiere_admin
def baja_sala(id):
    _, error = llamar("DELETE", f"/api/admin/salas/{id}")
    if error:
        flash(error["mensaje"], "error")
        return redirect(url_for("backoffice.sala", id=id))
    flash("Quitaste la sala: ya no se pueden programar funciones en ella.", "exito")
    return redirect(url_for("backoffice.locales"))


@backoffice_bp.context_processor
def menu_admin():
    return {"secciones_admin": SECCIONES}


@backoffice_bp.get("/")
@requiere_admin
def inicio():
    return redirect(url_for("backoffice.dashboards"))


# Dashboards maquetados (SCRUM-121) con datos de ejemplo que tienen la forma de las respuestas de
# GET /api/admin/dashboards/{ocupacion,ventas-genero,franjas-horarias,cancelaciones}. SCRUM-77 reemplaza
# _dashboards_ejemplo por un llamar(...) a cada endpoint con los filtros desde / hasta; el resumen de los KPI sale
# de esas mismas respuestas (entradas, monto, ocupación y porcentaje de cancelación).
def _dashboards_ejemplo():
    return {
        "resumen": {
            "entradas": 1742, "entradas_variacion": 12, "monto": 4820000.00, "monto_variacion": 8,
            "ocupacion": 68, "ocupacion_variacion": -3, "cancelaciones": 4.2, "cancelaciones_variacion": 0.6,
        },
        "franjas_horarias": [
            {"franja": "12 a 15 h", "entradas": 180}, {"franja": "15 a 18 h", "entradas": 310},
            {"franja": "18 a 21 h", "entradas": 742}, {"franja": "21 a 24 h", "entradas": 510},
        ],
        "ocupacion": [
            {"pelicula": "La noche del telón", "vendidas": 412, "capacidad": 560, "ocupacion": 74},
            {"pelicula": "Código Medianoche", "vendidas": 330, "capacidad": 500, "ocupacion": 66},
            {"pelicula": "Pequeños gigantes", "vendidas": 245, "capacidad": 400, "ocupacion": 61},
            {"pelicula": "El jardín de cristal", "vendidas": 120, "capacidad": 240, "ocupacion": 50},
        ],
        "ventas_genero": [
            {"genero": "Drama", "entradas": 620, "monto": 1705000.00},
            {"genero": "Ciencia ficción", "entradas": 510, "monto": 1402500.00},
            {"genero": "Animación", "entradas": 380, "monto": 1045000.00},
            {"genero": "Comedia", "entradas": 232, "monto": 667500.00},
        ],
        "cancelaciones": [
            {"pelicula": "Código Medianoche", "cancelaciones": 18, "porcentaje": 6.1},
            {"pelicula": "La noche del telón", "cancelaciones": 14, "porcentaje": 3.4},
            {"pelicula": "Pequeños gigantes", "cancelaciones": 7, "porcentaje": 2.9},
        ],
    }


@backoffice_bp.get("/dashboards")
@requiere_admin
def dashboards():
    return render_template("backoffice/dashboards.html", **_dashboards_ejemplo())


CAMPOS_EDICION_PELICULA = (
    "titulo", "sinopsis", "poster_url", "duracion_min", "clasificacion", "genero", "disponible_desde", "disponible_hasta",
)


def _listar_peliculas():
    peliculas, error = llamar("GET", "/api/admin/peliculas")

    if error is not None:
        flash(error["mensaje"], "error")
        return []

    return peliculas


@backoffice_bp.get("/peliculas")
@requiere_admin
def peliculas():
    consulta = request.args.get("q", "").strip()
    resultados = []

    if consulta:
        resultados, error = llamar(
            "GET",
            "/api/admin/tmdb/buscar",
            params={"q": consulta},
        )

        if error is not None:
            flash(error["mensaje"], "error")
            resultados = []

    return render_template(
        "backoffice/peliculas.html",
        peliculas=_listar_peliculas(),
        consulta=consulta,
        resultados=resultados,
    )

@backoffice_bp.post("/peliculas/importar")
@requiere_admin
def importar_pelicula():
    formulario = leer_formulario(
        request.form,
        "tmdb_id",
        "disponible_desde",
        "disponible_hasta",
        "q",
    )

    try:
        tmdb_id = int(formulario["tmdb_id"])
    except ValueError:
        flash("La película seleccionada no es válida.", "error")
        return redirect(url_for("backoffice.peliculas"))

    pelicula, error = llamar(
        "POST",
        "/api/admin/peliculas",
        json={
            "tmdb_id": tmdb_id,
            "disponible_desde": formulario["disponible_desde"] + ":00",
            "disponible_hasta": formulario["disponible_hasta"] + ":00",
},
    )

    if error is not None:
        flash(error["mensaje"], "error")
        return redirect(
            url_for("backoffice.peliculas", q=formulario["q"])
        )

    flash(f"Importaste {pelicula['titulo']}.", "exito")
    return redirect(url_for("backoffice.peliculas"))

@backoffice_bp.route("/peliculas/<int:id>/editar", methods=["GET", "POST"])
@requiere_admin
def editar_pelicula(id):
    if request.method == "GET":
        pelicula, error = llamar("GET", f"/api/admin/peliculas/{id}")

        if error is not None:
            flash(error["mensaje"], "error")
            return redirect(url_for("backoffice.peliculas"))

        formulario = {
            campo: pelicula.get(campo) or ""
            for campo in CAMPOS_EDICION_PELICULA
        }

        return render_template(
            "backoffice/pelicula_editar.html",
            pelicula=pelicula,
            formulario=formulario,
        )

    formulario = leer_formulario(
        request.form,
        *CAMPOS_EDICION_PELICULA,
    )

    try:
        duracion_min = int(formulario["duracion_min"])
    except ValueError:
        flash("La duración debe ser un número entero de minutos.", "error")
        pelicula = {"id": id, "titulo": formulario["titulo"]}

        return render_template(
            "backoffice/pelicula_editar.html",
            pelicula=pelicula,
            formulario=formulario,
        ), 400

    datos = {
        "titulo": formulario["titulo"],
        "sinopsis": formulario["sinopsis"] or None,
        "poster_url": formulario["poster_url"] or None,
        "duracion_min": duracion_min,
        "clasificacion": formulario["clasificacion"] or None,
        "genero": formulario["genero"],
        "disponible_desde": formulario["disponible_desde"] + ":00" if len(formulario["disponible_desde"]) == 16 else formulario["disponible_desde"],
        "disponible_hasta": formulario["disponible_hasta"] + ":00" if len(formulario["disponible_hasta"]) == 16 else formulario["disponible_hasta"],
    }

    pelicula, error = llamar(
        "PATCH",
        f"/api/admin/peliculas/{id}",
        json=datos,
    )

    if error is not None:
        flash(error["mensaje"], "error")
        pelicula = {"id": id, "titulo": formulario["titulo"]}

        return render_template(
            "backoffice/pelicula_editar.html",
            pelicula=pelicula,
            formulario=formulario,
        ), error["status"]

    flash(f"Guardaste los cambios de {pelicula['titulo']}.", "exito")
    return redirect(url_for("backoffice.peliculas"))


@backoffice_bp.post("/peliculas/<int:id>/baja")
@requiere_admin
def baja_pelicula(id):
    resultado, error = llamar(
        "DELETE",
        f"/api/admin/peliculas/{id}",
    )

    if error is not None:
        flash(error["mensaje"], "error")
        return redirect(url_for("backoffice.peliculas"))

    if resultado["baja"] == "logica":
        flash("La película quedó inactiva.", "exito")
    else:
        flash("La película fue eliminada.", "exito")

    return redirect(url_for("backoffice.peliculas"))

# Validar ingreso (SCRUM-74). El QR del email codifica /admin/ingreso?token=<token_qr>: la cámara del celular abre
# esta página con el código cargado; sin cámara, se pega en el mismo campo. El GET solo muestra el formulario
# (abrir o recargar la URL del QR no gasta la entrada): valida el POST del botón. La función que se controla no
# viene en el QR, así que se elige una vez y queda en la sesión del frontend.
MOTIVOS_RECHAZO = {
    "QR_INVALIDO": "QR inválido",
    "CANCELADA": "Compra cancelada",
    "YA_UTILIZADA": "Entrada ya utilizada",
    "OTRA_FUNCION": "Es de otra función",
    "FUERA_DE_FECHA": "Fuera de fecha",
}


def _funciones_de_hoy():
    """Opciones {"valor", "texto"} con las funciones de hoy, para elegir la que se controla en la puerta."""
    hoy = date.today().isoformat()
    funciones, error = llamar(
        "GET", "/api/admin/funciones", params={"desde": f"{hoy}T00:00:00", "hasta": f"{hoy}T23:59:59"},
    )
    if error is not None:
        flash(error["mensaje"], "error")
        funciones = []
    return [{"valor": "", "texto": "Elegí la función"}] + [
        {"valor": funcion["id"], "texto": f"{hora(funcion['fecha_hora'])} · {funcion['pelicula']} · "
                                          f"{funcion['local']}, {funcion['sala']}"}
        for funcion in funciones
    ]


def _validar_ingreso(formulario):
    """Valida el QR en la API. Devuelve el resultado para mostrar, o None si el error no es un rechazo del QR
    (por ejemplo, el backend caído), que ya queda avisado con flash."""
    entrada, error = llamar(
        "POST", "/api/admin/ingresos/validar",
        json={"token_qr": formulario["token"], "funcion_id": int(formulario["funcion_id"])},
    )
    if error is None:
        return {**entrada, "valido": True}
    if error["codigo"] in MOTIVOS_RECHAZO:
        return {"valido": False, "motivo": MOTIVOS_RECHAZO[error["codigo"]], "mensaje": error["mensaje"]}
    flash(error["mensaje"], "error")
    return None


def _historial_ingresos(funcion_id):
    """Últimos intentos de validación (SCRUM-125), de la función que se controla si ya se eligió una."""
    params = {"limite": 20}
    if funcion_id:
        params["funcion_id"] = funcion_id
    historial, error = llamar("GET", "/api/admin/ingresos", params=params)
    if error is not None:
        flash(error["mensaje"], "error")
        return []
    return historial


@backoffice_bp.route("/ingreso", methods=["GET", "POST"])
@requiere_admin
def ingreso():
    if request.method == "GET":
        formulario = {"funcion_id": session.get("funcion_ingreso", ""), "token": request.args.get("token", "").strip()}
        errores = {}
        resultado = None
    else:
        formulario = leer_formulario(request.form, "funcion_id", "token")
        errores = validar_ingreso(formulario)
        if "funcion_id" not in errores:
            session["funcion_ingreso"] = int(formulario["funcion_id"])
        resultado = None if errores else _validar_ingreso(formulario)
        if resultado is not None:
            formulario["token"] = ""  # el campo queda vacío para el próximo QR
    pagina = render_template(
        "backoffice/ingreso.html",
        funciones=_funciones_de_hoy(), formulario=formulario, errores=errores, resultado=resultado,
        historial=_historial_ingresos(session.get("funcion_ingreso")),
    )
    return pagina, 400 if errores else 200


# ABM de servicios maquetado (SCRUM-120) con datos de ejemplo que tienen la forma de la respuesta de
# GET /api/admin/servicios. SCRUM-72 reemplaza servicios_ejemplo y los flash de "guardado" por llamar(...).
CAMPOS_SERVICIO = ("nombre", "descripcion", "precio")


def _precio_para_campo(precio):
    """6500.0 o "6500.00" (DECIMAL serializado) -> "6500" para el input numérico; 6500.5 -> "6500.5"."""
    return f"{float(precio):.2f}".rstrip("0").rstrip(".")


def _listar_servicios():
    servicios, error = llamar("GET", "/api/admin/servicios")

    if error is not None:
        flash(error["mensaje"], "error")
        return []

    return servicios


def _abm_servicios(servicio=None):
    if request.method == "POST":
        formulario = leer_formulario(request.form, *CAMPOS_SERVICIO)
        errores = validar_servicio(formulario)

        if not errores:
            datos = {
                "nombre": formulario["nombre"],
                "descripcion": formulario["descripcion"] or None,
                "precio": float(formulario["precio"].replace(",", ".")),
            }

            if servicio is None:
                metodo = "POST"
                ruta = "/api/admin/servicios"
            else:
                metodo = "PUT"
                ruta = f"/api/admin/servicios/{servicio['id']}"

            resultado, error = llamar(metodo, ruta, json=datos)

            if error is None:
                flash("El servicio se guardó correctamente.", "exito")
                return redirect(url_for("backoffice.servicios"))

            flash(error["mensaje"], "error")
    else:
        formulario = {
            campo: (servicio or {}).get(campo) or ""
            for campo in CAMPOS_SERVICIO
        }

        if servicio:
            formulario["precio"] = _precio_para_campo(servicio["precio"])

        errores = {}

    pagina = render_template(
        "backoffice/servicios.html",
        servicios=_listar_servicios(),
        servicio=servicio,
        formulario=formulario,
        errores=errores,
    )

    return pagina, 400 if errores else 200


@backoffice_bp.route("/servicios", methods=["GET", "POST"])
@requiere_admin
def servicios():
    return _abm_servicios()


@backoffice_bp.route("/servicios/<int:id>", methods=["GET", "POST"])
@requiere_admin
def editar_servicio(id):
    servicio = next(
        (s for s in _listar_servicios() if s["id"] == id),
        None,
    )

    if servicio is None:
        flash("Ese servicio no existe.", "error")
        return redirect(url_for("backoffice.servicios"))

    return _abm_servicios(servicio)


@backoffice_bp.post("/servicios/<int:id>/baja")
@requiere_admin
def baja_servicio(id):
    resultado, error = llamar(
        "DELETE", f"/api/admin/servicios/{id}"
    )

    if error is not None:
        flash(error["mensaje"], "error")
    else:
        flash("El servicio quedó inactivo.", "exito")

    return redirect(url_for("backoffice.servicios"))


@backoffice_bp.post("/servicios/<int:id>/reactivar")
@requiere_admin
def reactivar_servicio(id):
    resultado, error = llamar(
        "POST", f"/api/admin/servicios/{id}/reactivar"
    )
    if error is not None:
        flash(error["mensaje"], "error")
    else:
        flash("El servicio quedó activo.", "exito")
    return redirect(url_for("backoffice.servicios"))


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
