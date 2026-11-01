"""Cartelera pública, detalle de películas, funciones y butacas (SCRUM-20, SCRUM-21).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, jsonify, request

from src.backend.services import cartelera

cartelera_bp = Blueprint("cartelera", __name__, url_prefix="/api")


@cartelera_bp.get("/cartelera")
def obtener_cartelera():
    return jsonify(cartelera.listar(request.args.get("local_id"), request.args.get("fecha")))


@cartelera_bp.get("/peliculas/<int:pelicula_id>")
def obtener_pelicula(pelicula_id):
    return jsonify(cartelera.obtener_pelicula(pelicula_id))


@cartelera_bp.get("/funciones/<int:funcion_id>/butacas")
def obtener_butacas(funcion_id):
    return jsonify(cartelera.mapa_de_butacas(funcion_id))
