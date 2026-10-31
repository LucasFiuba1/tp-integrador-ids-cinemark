"""ABM de películas, locales, salas, funciones, servicios y validación de QR (SCRUM-19, 22, 23, 27, 28).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, jsonify, request

from src.backend.auth import requiere_rol
from src.backend.services import peliculas

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/tmdb/buscar")
@requiere_rol("admin")
def buscar_tmdb():
    return jsonify(peliculas.buscar_en_tmdb(request.args.get("q")))


@admin_bp.get("/peliculas")
@requiere_rol("admin")
def listar_peliculas():
    return jsonify(peliculas.listar())


@admin_bp.get("/peliculas/<int:pelicula_id>")
@requiere_rol("admin")
def obtener_pelicula(pelicula_id):
    return jsonify(peliculas.obtener(pelicula_id))
