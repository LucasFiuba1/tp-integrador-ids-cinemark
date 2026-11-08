"""Páginas del administrador (ABM, dashboards y validación de QR)."""
from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from src.frontend.api_client import llamar
from src.frontend.ejemplos import servicios_ejemplo
from src.frontend.filtros import hora
from src.frontend.sesion import requiere_admin
from src.frontend.validaciones import leer_formulario, validar_filtros_dashboards, validar_ingreso, validar_servicio

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

# Programación de funciones del backoffice (SCRUM-57).

def _local_elegido(locales, local_id):
    for local in locales:
        if local["id"] == local_id:
            return local
    if locales:
        return locales[0]
    return None


@backoffice_bp.get("/locales")
@requiere_admin
def locales():
    return render_template(
        "backoffice/locales.html",
        locales=_locales_ejemplo()
    )

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


@backoffice_bp.context_processor
def menu_admin():
    return {"secciones_admin": SECCIONES}


@backoffice_bp.get("/")
@requiere_admin
def inicio():
    return redirect(url_for("backoffice.dashboards"))


# Tableros de los dashboards: (variable del template, ruta de GET /api/admin/dashboards/<ruta>).
TABLEROS = (
    ("ocupacion", "ocupacion"),
    ("ventas_genero", "ventas-genero"),
    ("franjas_horarias", "franjas-horarias"),
    ("cancelaciones", "cancelaciones"),
)
DIAS_POR_DEFECTO = 7  # sin filtros se muestran los últimos 7 días, hoy incluido
FUNCIONES_EN_TABLA = 10  # la API las devuelve de mayor a menor ocupación


def _filtros_dashboards(args):
    """Lee los filtros del formulario GET; las fechas vacías toman el período por defecto.

    local_id sale de un select, así que un valor que no es un id solo llega editando la URL: se toma como "todos".
    """
    filtros = leer_formulario(args, "desde", "hasta", "local_id")
    hoy = date.today()
    filtros["desde"] = filtros["desde"] or (hoy - timedelta(days=DIAS_POR_DEFECTO - 1)).isoformat()
    filtros["hasta"] = filtros["hasta"] or hoy.isoformat()
    filtros["local_id"] = filtros["local_id"] if filtros["local_id"].isdigit() else ""
    return filtros


def _parametros_dashboards(filtros):
    """La API espera DATETIME ISO: el período abarca los días desde y hasta completos."""
    parametros = {"desde": f"{filtros['desde']}T00:00:00", "hasta": f"{filtros['hasta']}T23:59:59"}
    if filtros["local_id"]:
        parametros["local_id"] = filtros["local_id"]
    return parametros


def _porcentaje(parte, total):
    return round(parte / total * 100, 1) if total else 0


def _franjas_para_columnas(franjas):
    """La API ordena las franjas por ventas; el gráfico de columnas las muestra en orden horario."""
    return [{"franja": f"{fila['hora_desde']} a {fila['hora_hasta']} h", "entradas": fila["entradas"]}
            for fila in sorted(franjas, key=lambda fila: fila["hora_desde"])]


def _resumen_dashboards(ocupacion, ventas_genero, cancelaciones):
    """KPI del período a partir de las mismas respuestas de los tableros (sin otra llamada a la API)."""
    return {
        "entradas": sum(fila["entradas"] for fila in ventas_genero),
        "monto": sum(fila["monto"] for fila in ventas_genero),
        "ocupacion": _porcentaje(sum(fila["vendidas"] for fila in ocupacion),
                                 sum(fila["capacidad"] for fila in ocupacion)),
        "cancelaciones": _porcentaje(sum(fila["canceladas"] for fila in cancelaciones),
                                     sum(fila["compras"] for fila in cancelaciones)),
    }


def _llamar_dashboards(filtros, errores):
    """Pide los locales (para el filtro) y, si los filtros son válidos, los cuatro tableros.

    Un tablero que falla queda vacío y su mensaje se muestra una sola vez (si el backend no responde, los cuatro
    fallan con el mismo mensaje).
    """
    locales, error = llamar("GET", "/api/admin/locales")
    fallas = [error] if error else []
    respuestas = {}
    if not errores:
        parametros = _parametros_dashboards(filtros)
        for clave, ruta in TABLEROS:
            respuestas[clave], error = llamar("GET", f"/api/admin/dashboards/{ruta}", params=parametros)
            fallas += [error] if error else []
    for mensaje in dict.fromkeys(falla["mensaje"] for falla in fallas):
        flash(mensaje, "error")
    return locales or [], respuestas


@backoffice_bp.get("/dashboards")
@requiere_admin
def dashboards():
    filtros = _filtros_dashboards(request.args)
    errores = validar_filtros_dashboards(filtros)
    locales, respuestas = _llamar_dashboards(filtros, errores)
    ocupacion = respuestas.get("ocupacion") or {}
    cancelaciones = respuestas.get("cancelaciones") or {}
    tableros = {
        "ocupacion": ocupacion.get("por_pelicula", []),
        "ocupacion_funciones": ocupacion.get("por_funcion", [])[:FUNCIONES_EN_TABLA],
        "ventas_genero": respuestas.get("ventas_genero") or [],
        "franjas_horarias": _franjas_para_columnas(respuestas.get("franjas_horarias") or []),
        "cancelaciones": cancelaciones.get("por_pelicula", []),
    }
    opciones_locales = [{"valor": "", "texto": "Todos los locales"}] + [
        {"valor": local["id"], "texto": local["nombre"]} for local in locales
    ]
    pagina = render_template(
        "backoffice/dashboards.html", filtros=filtros, errores=errores, opciones_locales=opciones_locales,
        resumen=_resumen_dashboards(tableros["ocupacion"], tableros["ventas_genero"], tableros["cancelaciones"]),
        **tableros,
    )
    return pagina, 400 if errores else 200


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


def _abm_servicios(servicio=None):
    """Listado + formulario de alta (servicio=None) o de edición. En POST valida y, si está bien, vuelve al listado."""
    if request.method == "POST":
        formulario = leer_formulario(request.form, *CAMPOS_SERVICIO)
        errores = validar_servicio(formulario)
        if not errores:
            flash(f"Guardaste el servicio {formulario['nombre']}.", "exito")
            return redirect(url_for("backoffice.servicios"))
    else:
        formulario = {campo: (servicio or {}).get(campo, "") for campo in CAMPOS_SERVICIO}
        if servicio:
            formulario["precio"] = _precio_para_campo(servicio["precio"])
        errores = {}
    pagina = render_template(
        "backoffice/servicios.html",
        servicios=servicios_ejemplo(), servicio=servicio, formulario=formulario, errores=errores,
    )
    return pagina, 400 if errores else 200


@backoffice_bp.route("/servicios", methods=["GET", "POST"])
@requiere_admin
def servicios():
    return _abm_servicios()


@backoffice_bp.route("/servicios/<int:id>", methods=["GET", "POST"])
@requiere_admin
def editar_servicio(id):
    servicio = next((s for s in servicios_ejemplo() if s["id"] == id), None)
    if servicio is None:
        flash("Ese servicio no existe.", "error")
        return redirect(url_for("backoffice.servicios"))
    return _abm_servicios(servicio)


@backoffice_bp.post("/servicios/<int:id>/baja")
@requiere_admin
def baja_servicio(id):
    flash("Quitaste el servicio: ya no se ofrece en las compras nuevas.", "exito")
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
