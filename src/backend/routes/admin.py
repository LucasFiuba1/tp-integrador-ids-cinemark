"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.errores import error_api
from src.backend.services import peliculas

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _cuerpo_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        error_api(400, "DATOS_INVALIDOS", "El cuerpo debe ser un objeto JSON.")
    return datos


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
    return jsonify(peliculas.importar(_cuerpo_json())), 201


@admin_bp.get("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def obtener_pelicula(pelicula_id):
    return jsonify(peliculas.obtener(pelicula_id))


@admin_bp.put("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def modificar_pelicula(pelicula_id):
    return jsonify(peliculas.modificar(pelicula_id, _cuerpo_json()))


@admin_bp.delete("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def eliminar_pelicula(pelicula_id):
    return jsonify(peliculas.dar_de_baja(pelicula_id))
