"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""

from flask import Blueprint, jsonify, request

from src.backend.abm import requerir_existente, traducir_duplicado
from src.backend.auth import requiere_rol
from src.backend.errores import respuesta_error
from src.backend.routes.comun import cuerpo_json
from src.backend.services import dashboards, funciones, ingresos, locales, peliculas, salas, servicios
from src.backend.services.validaciones import entero_positivo

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

MENSAJE_LOCAL_DUPLICADO = "Ya existe un local con ese nombre o dirección."
MENSAJE_SALA_DUPLICADA = "Ya existe una sala con ese nombre en el local."
MENSAJE_SERVICIO_DUPLICADO = "Ya existe un servicio con ese nombre."
MENSAJE_LOCAL_INEXISTENTE = "El local no existe."
MENSAJE_SALA_INEXISTENTE = "La sala no existe."
MENSAJE_SERVICIO_INEXISTENTE = "El servicio no existe."


@admin_bp.get("/locales")
@requiere_rol("admin")
def listar_locales():
    return jsonify(locales.listar_locales())


@admin_bp.post("/locales")
@requiere_rol("admin")
def crear_local():
    datos = cuerpo_json()
    nombre, direccion = locales.validar_local(datos.get("nombre"), datos.get("direccion"))
    with traducir_duplicado(MENSAJE_LOCAL_DUPLICADO, "LOCAL_DUPLICADO"):
        local = locales.crear_local(nombre, direccion)
    return jsonify(local), 201


@admin_bp.put("/locales/<int:local_id>")
@requiere_rol("admin")
def modificar_local(local_id):
    requerir_existente(locales.obtener_local(local_id), MENSAJE_LOCAL_INEXISTENTE)
    datos = cuerpo_json()
    nombre, direccion = locales.validar_local(datos.get("nombre"), datos.get("direccion"))
    with traducir_duplicado(MENSAJE_LOCAL_DUPLICADO, "LOCAL_DUPLICADO"):
        local = locales.modificar_local(local_id, nombre, direccion)
    return jsonify(local)


@admin_bp.delete("/locales/<int:local_id>")
@requiere_rol("admin")
def eliminar_local(local_id):
    requerir_existente(locales.obtener_local(local_id), MENSAJE_LOCAL_INEXISTENTE)
    if locales.local_tiene_salas_activas(local_id):
        return respuesta_error(409, "LOCAL_CON_SALAS", "No se puede eliminar un local que tiene salas activas.")
    if locales.local_tiene_funciones(local_id):
        return respuesta_error(
            409, "LOCAL_CON_HISTORIAL", "No se puede eliminar el local: tiene salas dadas de baja con funciones registradas."
        )
    locales.eliminar_local(local_id)
    return "", 204


@admin_bp.get("/salas")
@requiere_rol("admin")
def listar_salas():
    local_id = request.args.get("local_id", type=int)
    return jsonify(salas.listar_salas(local_id))


@admin_bp.post("/salas")
@requiere_rol("admin")
def crear_sala():
    datos = cuerpo_json()
    local_id = entero_positivo(datos.get("local_id"), "local_id")
    nombre, filas, columnas = salas.validar_salas(datos.get("nombre"), datos.get("filas"), datos.get("columnas"))
    requerir_existente(locales.obtener_local(local_id), MENSAJE_LOCAL_INEXISTENTE)
    with traducir_duplicado(MENSAJE_SALA_DUPLICADA, "SALA_DUPLICADA"):
        sala = salas.crear_sala(local_id, nombre, filas, columnas)
    return jsonify(sala), 201


@admin_bp.get("/salas/<int:sala_id>")
@requiere_rol("admin")
def detalle_sala(sala_id):
    sala = requerir_existente(salas.obtener_sala(sala_id), MENSAJE_SALA_INEXISTENTE)
    return jsonify({**sala, "butacas": salas.listar_butacas(sala_id)})


@admin_bp.put("/salas/<int:sala_id>")
@requiere_rol("admin")
def modificar_sala(sala_id):
    sala = requerir_existente(salas.obtener_sala(sala_id), MENSAJE_SALA_INEXISTENTE)
    datos = cuerpo_json()
    nombre, filas, columnas = salas.validar_salas(datos.get("nombre"), datos.get("filas"), datos.get("columnas"))
    se_achica_la_sala = filas < sala["filas"] or columnas < sala["columnas"]
    if se_achica_la_sala and salas.tiene_funciones_futuras(sala_id):
        return respuesta_error(409, "SALA_CON_FUNCIONES", "No se puede reducir una sala con funciones futuras.")
    if se_achica_la_sala and salas.hay_entradas_en_butacas_eliminadas(sala_id, filas, columnas):
        return respuesta_error(409, "BUTACAS_CON_ENTRADAS", "Hay entradas vendidas en las butacas que se quitarían.")
    with traducir_duplicado(MENSAJE_SALA_DUPLICADA, "SALA_DUPLICADA"):
        res = salas.modificar_sala(sala_id, nombre, filas, columnas, sala)
    return jsonify(res)


@admin_bp.delete("/salas/<int:sala_id>")
@requiere_rol("admin")
def eliminar_sala(sala_id):
    requerir_existente(salas.obtener_sala(sala_id), MENSAJE_SALA_INEXISTENTE)
    if salas.tiene_funciones_futuras(sala_id):
        return respuesta_error(409, "SALA_CON_FUNCIONES", "No se puede dar de baja una sala con funciones futuras.")
    salas.eliminar_sala(sala_id)
    return "", 204


@admin_bp.get("/servicios")
@requiere_rol("admin")
def listar_servicios():
    return jsonify(servicios.listar_servicios())


@admin_bp.post("/servicios")
@requiere_rol("admin")
def crear_servicio():
    datos = cuerpo_json()
    nombre, descripcion, precio = servicios.validar_servicio(
        datos.get("nombre"), datos.get("descripcion"), datos.get("precio")
    )
    with traducir_duplicado(MENSAJE_SERVICIO_DUPLICADO, "SERVICIO_DUPLICADO"):
        servicio = servicios.crear_servicio(nombre, descripcion, precio)
    return jsonify(servicio), 201


@admin_bp.put("/servicios/<int:servicio_id>")
@requiere_rol("admin")
def modificar_servicio(servicio_id):
    servicio = requerir_existente(servicios.obtener_servicio(servicio_id), MENSAJE_SERVICIO_INEXISTENTE)
    datos = cuerpo_json()
    nombre, descripcion, precio = servicios.validar_servicio(
        datos.get("nombre"), datos.get("descripcion"), datos.get("precio")
    )
    with traducir_duplicado(MENSAJE_SERVICIO_DUPLICADO, "SERVICIO_DUPLICADO"):
        res = servicios.modificar_servicio(servicio_id, nombre, descripcion, precio, servicio["activo"])
    return jsonify(res)


@admin_bp.delete("/servicios/<int:servicio_id>")
@requiere_rol("admin")
def eliminar_servicio(servicio_id):
    requerir_existente(servicios.obtener_servicio(servicio_id), MENSAJE_SERVICIO_INEXISTENTE)
    servicios.dar_de_baja_servicio(servicio_id)
    return "", 204


@admin_bp.post("/servicios/<int:servicio_id>/reactivar")
@requiere_rol("admin")
def reactivar_servicio(servicio_id):
    requerir_existente(servicios.obtener_servicio(servicio_id), MENSAJE_SERVICIO_INEXISTENTE)
    servicios.reactivar_servicio(servicio_id)
    return "", 204


@admin_bp.get("/tmdb/buscar")
@requiere_rol("admin")
def buscar_tmdb():
    return jsonify(peliculas.buscar_en_tmdb(request.args.get("q")))


@admin_bp.get("/peliculas")
@requiere_rol("admin")
def listar_peliculas():
    return jsonify(peliculas.listar())


@admin_bp.post("/peliculas")
@requiere_rol("admin")
def importar_pelicula():
    return jsonify(peliculas.importar(cuerpo_json())), 201


@admin_bp.get("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def obtener_pelicula(pelicula_id):
    return jsonify(peliculas.obtener(pelicula_id))


@admin_bp.patch("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def modificar_pelicula(pelicula_id):
    return jsonify(peliculas.modificar(pelicula_id, cuerpo_json()))


@admin_bp.delete("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def eliminar_pelicula(pelicula_id):
    return jsonify(peliculas.dar_de_baja(pelicula_id))


@admin_bp.get("/funciones")
@requiere_rol("admin")
def listar_funciones():
    return jsonify(
        funciones.listar(
            request.args.get("local_id"),
            request.args.get("desde"),
            request.args.get("hasta"),
        )
    )


@admin_bp.post("/funciones")
@requiere_rol("admin")
def crear_funcion():
    return jsonify(funciones.crear(cuerpo_json())), 201


@admin_bp.put("/funciones/<int:funcion_id>")
@requiere_rol("admin")
def modificar_funcion(funcion_id):
    return jsonify(funciones.modificar(funcion_id, cuerpo_json()))


@admin_bp.delete("/funciones/<int:funcion_id>")
@requiere_rol("admin")
def eliminar_funcion(funcion_id):
    return jsonify(funciones.dar_de_baja(funcion_id))


def _filtros_dashboard():
    return request.args.get("desde"), request.args.get("hasta"), request.args.get("local_id")


@admin_bp.get("/dashboards/resumen")
@requiere_rol("admin")
def dashboard_resumen():
    return jsonify(dashboards.resumen_dashboard(*_filtros_dashboard()))


@admin_bp.get("/dashboards/ocupacion")
@requiere_rol("admin")
def dashboard_ocupacion():
    return jsonify(dashboards.listar_ocupacion(*_filtros_dashboard()))


@admin_bp.get("/dashboards/ventas-genero")
@requiere_rol("admin")
def dashboard_ventas_genero():
    return jsonify(dashboards.listar_ventas_genero(*_filtros_dashboard()))


@admin_bp.get("/dashboards/franjas-horarias")
@requiere_rol("admin")
def dashboard_franjas_horarias():
    return jsonify(dashboards.listar_franjas_horarias(*_filtros_dashboard()))


@admin_bp.get("/dashboards/cancelaciones")
@requiere_rol("admin")
def dashboard_cancelaciones():
    return jsonify(dashboards.listar_cancelaciones(*_filtros_dashboard()))


@admin_bp.get("/ingresos")
@requiere_rol("admin")
def listar_ingresos():
    return jsonify(ingresos.listar(request.args.get("funcion_id"), request.args.get("limite")))


@admin_bp.post("/ingresos/validar")
@requiere_rol("admin")
def validar_ingreso():
    return jsonify(ingresos.validar(cuerpo_json()))
