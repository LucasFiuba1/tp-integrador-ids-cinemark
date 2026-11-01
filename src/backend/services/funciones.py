"""Consultas públicas de funciones y disponibilidad de butacas."""
from src.backend.db import consultar, consultar_uno
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


def obtener_butacas(funcion_id):
    funcion = consultar_uno(
        "SELECT f.sala_id, f.fecha_hora, s.nombre AS sala "
        "FROM funciones f JOIN salas s ON s.id = f.sala_id "
        "WHERE f.id = %s AND f.activa = TRUE AND s.activa = TRUE AND f.fecha_hora > NOW()",
        (funcion_id,),
    )
    if funcion is None:
        error_api(404, "NO_ENCONTRADO", "La función no existe o ya comenzó.")
    butacas = consultar(
        "SELECT b.id, b.fila, b.numero, "
        "CASE WHEN EXISTS ("
        "SELECT 1 FROM entradas e JOIN compras c ON c.id = e.compra_id "
        "WHERE e.butaca_id = b.id AND e.funcion_id = %s AND e.activa = 1 "
        "AND (c.estado = 'confirmada' OR (c.estado = 'pendiente' AND c.vence_en > NOW()))"
        ") THEN 'ocupada' ELSE 'libre' END AS estado "
        "FROM butacas b WHERE b.sala_id = %s ORDER BY b.fila, b.numero",
        (funcion_id, funcion["sala_id"]),
    )
    libres = sum(butaca["estado"] == "libre" for butaca in butacas)
    return {
        "funcion_id": funcion_id,
        "sala": funcion["sala"],
        "capacidad": len(butacas),
        "libres": libres,
        "vendible": libres > 0,
        "butacas": butacas,
    }
