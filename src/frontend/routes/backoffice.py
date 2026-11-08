"""Páginas del administrador (ABM, dashboards y validación de QR)."""
from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.frontend.api_client import llamar
from src.frontend.ejemplos import servicios_ejemplo
from src.frontend.sesion import requiere_admin
from src.frontend.validaciones import (
    leer_formulario, validar_codigo_qr, validar_filtros_dashboards, validar_servicio,
)

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
SECCIONES_IMPLEMENTADAS = ("dashboards", "locales", "servicios", "validar")


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


# Tableros de los dashboards: (variable del template, ruta de GET /api/admin/dashboards/<ruta>).
TABLEROS = (
    ("ocupacion", "ocupacion"),
    ("ventas_genero", "ventas-genero"),
    ("franjas_horarias", "franjas-horarias"),
    ("cancelaciones", "cancelaciones"),
)
DIAS_POR_DEFECTO = 7  # sin filtros se muestran los últimos 7 días, hoy incluido


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


def _resumen_dashboards(ocupacion, ventas_genero, cancelaciones):
    """KPI del período a partir de las mismas respuestas de los tableros (sin otra llamada a la API)."""
    return {
        "entradas": sum(fila["entradas"] for fila in ventas_genero),
        "monto": sum(fila["monto"] for fila in ventas_genero),
        "ocupacion": _porcentaje(sum(fila["vendidas"] for fila in ocupacion),
                                 sum(fila["capacidad"] for fila in ocupacion)),
        "cancelaciones": _porcentaje(sum(fila["cancelaciones"] for fila in cancelaciones),
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
    tableros = {
        "ocupacion": ocupacion.get("por_pelicula", []),
        "ocupacion_funciones": ocupacion.get("por_funcion", []),
        "ventas_genero": respuestas.get("ventas_genero") or [],
        "franjas_horarias": respuestas.get("franjas_horarias") or [],
        "cancelaciones": respuestas.get("cancelaciones") or [],
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
    if request.form.get("compra_id", "").isdecimal():
        flash("Ingreso confirmado: el QR quedó marcado como usado.", "exito")
    else:
        flash("No se pudo confirmar el ingreso. Volvé a validar el código.", "error")
    return redirect(url_for("backoffice.validar"))


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
