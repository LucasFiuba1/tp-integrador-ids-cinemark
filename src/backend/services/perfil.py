"""Perfil del cliente: historial de compras y películas vistas (SCRUM-49).

Todas las consultas filtran por el usuario del token (g.usuario), que recibe la ruta:
nunca por un id que mande el cliente, así nadie puede ver compras ajenas.
"""
from datetime import datetime, timedelta

from flask import current_app

from src.backend.db import consultar


def _iso(fecha):
    return fecha.isoformat() if fecha is not None else None


def es_cancelable(estado, fecha_funcion, utilizada_en):
    limite = fecha_funcion - timedelta(hours=current_app.config["HORAS_LIMITE_CANCELACION"])
    return estado == "confirmada" and utilizada_en is None and datetime.now() < limite


def _agrupar_por_compra(filas, convertir):
    agrupado = {}
    for fila in filas:
        agrupado.setdefault(fila["compra_id"], []).append(convertir(fila))
    return agrupado


def listar_compras(usuario_id):
    compras = consultar(
        "SELECT c.id, c.estado, c.total, c.token_qr, c.creada_en, c.confirmada_en, c.cancelada_en, "
        "c.utilizada_en, f.id AS funcion_id, f.fecha_hora, p.titulo, p.poster_url, "
        "s.nombre AS sala, l.nombre AS local "
        "FROM compras c "
        "JOIN funciones f ON f.id = c.funcion_id "
        "JOIN peliculas p ON p.id = f.pelicula_id "
        "JOIN salas s ON s.id = f.sala_id "
        "JOIN locales l ON l.id = s.local_id "
        "WHERE c.usuario_id = %s AND c.estado IN ('confirmada', 'cancelada') "
        "ORDER BY f.fecha_hora DESC",
        (usuario_id,),
    )
    butacas = _agrupar_por_compra(
        consultar(
            "SELECT e.compra_id, b.fila, b.numero FROM entradas e "
            "JOIN butacas b ON b.id = e.butaca_id "
            "JOIN compras c ON c.id = e.compra_id "
            "WHERE c.usuario_id = %s ORDER BY b.fila, b.numero",
            (usuario_id,),
        ),
        lambda fila: fila["fila"] + str(fila["numero"]),
    )
    servicios = _agrupar_por_compra(
        consultar(
            "SELECT cs.compra_id, sv.nombre, cs.cantidad, cs.precio_unitario FROM compra_servicios cs "
            "JOIN servicios sv ON sv.id = cs.servicio_id "
            "JOIN compras c ON c.id = cs.compra_id "
            "WHERE c.usuario_id = %s ORDER BY sv.nombre",
            (usuario_id,),
        ),
        lambda fila: {
            "nombre": fila["nombre"],
            "cantidad": fila["cantidad"],
            "precio_unitario": float(fila["precio_unitario"]),
        },
    )

    resultado = []
    for compra in compras:
        resultado.append({
            "id": compra["id"],
            "estado": compra["estado"],
            "total": float(compra["total"]),
            "creada_en": _iso(compra["creada_en"]),
            "confirmada_en": _iso(compra["confirmada_en"]),
            "cancelada_en": _iso(compra["cancelada_en"]),
            "utilizada_en": _iso(compra["utilizada_en"]),
            "funcion": {
                "id": compra["funcion_id"],
                "fecha_hora": _iso(compra["fecha_hora"]),
                "pelicula": compra["titulo"],
                "poster_url": compra["poster_url"],
                "sala": compra["sala"],
                "local": compra["local"],
            },
            "butacas": butacas.get(compra["id"], []),
            "servicios": servicios.get(compra["id"], []),
            "token_qr": compra["token_qr"] if compra["estado"] == "confirmada" else None,
            "cancelable": es_cancelable(compra["estado"], compra["fecha_hora"], compra["utilizada_en"]),
        })
    return resultado


def listar_peliculas_vistas(usuario_id):
    """Una película cuenta como vista cuando el QR de su compra se validó en el ingreso (utilizada_en)."""
    filas = consultar(
        "SELECT p.id AS pelicula_id, p.titulo, p.poster_url, p.genero, f.fecha_hora, "
        "s.nombre AS sala, l.nombre AS local, c.utilizada_en "
        "FROM compras c "
        "JOIN funciones f ON f.id = c.funcion_id "
        "JOIN peliculas p ON p.id = f.pelicula_id "
        "JOIN salas s ON s.id = f.sala_id "
        "JOIN locales l ON l.id = s.local_id "
        "WHERE c.usuario_id = %s AND c.utilizada_en IS NOT NULL "
        "ORDER BY c.utilizada_en DESC",
        (usuario_id,),
    )
    for fila in filas:
        fila["fecha_hora"] = _iso(fila["fecha_hora"])
        fila["utilizada_en"] = _iso(fila["utilizada_en"])
    return filas
