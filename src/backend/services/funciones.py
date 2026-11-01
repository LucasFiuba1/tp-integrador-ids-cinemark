"""Detalle público de una función (el mapa de butacas está en services/cartelera.py)."""
from src.backend.db import consultar_uno
from src.backend.errores import error_api


def obtener(funcion_id):
    funcion = consultar_uno(
        "SELECT f.id, f.fecha_hora, f.precio, p.titulo AS pelicula, p.poster_url, "
        "s.id AS sala_id, s.nombre AS sala, l.nombre AS local "
        "FROM funciones f "
        "JOIN peliculas p ON p.id = f.pelicula_id "
        "JOIN salas s ON s.id = f.sala_id "
        "JOIN locales l ON l.id = s.local_id "
        "WHERE f.id = %s AND f.activa = TRUE AND p.activa = TRUE AND s.activa = TRUE "
        "AND f.fecha_hora > NOW()",
        (funcion_id,),
    )
    if funcion is None:
        error_api(404, "NO_ENCONTRADO", "La función no existe o ya comenzó.")
    funcion["fecha_hora"] = funcion["fecha_hora"].isoformat()
    funcion["precio"] = float(funcion["precio"])
    funcion.pop("sala_id")
    return funcion

