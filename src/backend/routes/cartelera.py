"""Cartelera pública, locales, detalle de películas, funciones, butacas y servicios (SCRUM-20, 21, 71, 126).

Los endpoints de este módulo están listados en docs/endpoints.md.
"""
from flask import Blueprint, jsonify, request

from src.backend.services import cartelera, funciones, locales, servicios

cartelera_bp = Blueprint("cartelera", __name__, url_prefix="/api")


@cartelera_bp.get("/locales")
def listar_locales():
    return jsonify(locales.listar_locales_publicos())


@cartelera_bp.get("/cartelera")
def obtener_cartelera():
    return jsonify(cartelera.listar(request.args.get("local_id"), request.args.get("fecha")))


@cartelera_bp.get("/peliculas/<int:pelicula_id>")
def obtener_pelicula(pelicula_id):
    return jsonify(cartelera.obtener_pelicula(pelicula_id))


@cartelera_bp.get("/funciones/<int:funcion_id>")
def obtener_funcion(funcion_id):
    return jsonify(funciones.obtener(funcion_id))


@cartelera_bp.get("/funciones/<int:funcion_id>/butacas")
def obtener_butacas(funcion_id):
    return jsonify(cartelera.mapa_de_butacas(funcion_id))


@cartelera_bp.get("/servicios")
def listar_servicios():
    return jsonify(servicios.listar_servicios_activos())
