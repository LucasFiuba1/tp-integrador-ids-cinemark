"""Reservas de butacas, detalle y cancelación de compras (SCRUM-62, SCRUM-69, SCRUM-70)."""
from datetime import datetime

import pymysql
from flask import current_app

from src.backend.db import consultar, consultar_uno, transaccion
from src.backend.errores import error_api
from src.backend.services.perfil import cancelable_hasta, es_cancelable
from src.backend.services.validaciones import entero_positivo, requerir_campos
from src.backend.tokens import leer_cancelacion


def reservar(usuario_id, datos):
    requerir_campos(datos, ("funcion_id", "butaca_ids"))
    funcion_id = entero_positivo(datos["funcion_id"], "funcion_id")
    butaca_ids = datos["butaca_ids"]
    if type(butaca_ids) is not list or not butaca_ids:
        error_api(400, "DATOS_INVALIDOS", "butaca_ids debe contener al menos una butaca.")
    if any(type(butaca_id) is not int or butaca_id <= 0 for butaca_id in butaca_ids):
        error_api(400, "DATOS_INVALIDOS", "Cada butaca_id debe ser un entero positivo.")
    if len(set(butaca_ids)) != len(butaca_ids):
        error_api(400, "DATOS_INVALIDOS", "No repitas una butaca en la reserva.")

    try:
        with transaccion() as cursor:
            cursor.execute(
                "SELECT f.sala_id, f.precio FROM funciones f "
                "JOIN peliculas p ON p.id = f.pelicula_id "
                "JOIN salas s ON s.id = f.sala_id "
                "WHERE f.id = %s AND f.activa = TRUE AND p.activa = TRUE AND s.activa = TRUE "
                "AND f.fecha_hora > NOW() FOR UPDATE",
                (funcion_id,),
            )
            funcion = cursor.fetchone()
            if funcion is None:
                error_api(404, "NO_ENCONTRADO", "La función no existe o ya comenzó.")

            cursor.execute(
                "UPDATE compras SET estado = 'vencida' "
                "WHERE funcion_id = %s AND estado = 'pendiente' AND vence_en <= NOW()",
                (funcion_id,),
            )
            cursor.execute(
                "UPDATE entradas e JOIN compras c ON c.id = e.compra_id "
                "SET e.activa = NULL WHERE c.funcion_id = %s AND c.estado = 'vencida' AND e.activa = 1",
                (funcion_id,),
            )

            marcadores = ", ".join(["%s"] * len(butaca_ids))
            cursor.execute(
                f"SELECT id FROM butacas WHERE sala_id = %s AND id IN ({marcadores})",
                (funcion["sala_id"], *butaca_ids),
            )
            butacas_validas = {fila["id"] for fila in cursor.fetchall()}
            if butacas_validas != set(butaca_ids):
                error_api(400, "DATOS_INVALIDOS", "Una o más butacas no pertenecen a la sala.")
            cursor.execute(
                "SELECT b.fila, b.numero FROM entradas e "
                "JOIN butacas b ON b.id = e.butaca_id "
                f"WHERE e.funcion_id = %s AND e.activa = 1 AND e.butaca_id IN ({marcadores}) "
                "ORDER BY b.fila, b.numero FOR UPDATE",
                (funcion_id, *butaca_ids),
            )
            ocupadas = cursor.fetchall()
            if ocupadas:
                nombres = ", ".join(f"{butaca['fila']}{butaca['numero']}" for butaca in ocupadas)
                error_api(409, "BUTACA_OCUPADA", f"Las butacas {nombres} ya fueron vendidas.")
            precio = funcion["precio"]
            total = precio * len(butaca_ids)
            cursor.execute(
                "INSERT INTO compras (usuario_id, funcion_id, estado, total, vence_en) "
                "VALUES (%s, %s, 'pendiente', %s, DATE_ADD(NOW(), INTERVAL %s MINUTE))",
                (usuario_id, funcion_id, total, current_app.config["MINUTOS_RESERVA"]),
            )
            compra_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio, activa) "
                "VALUES (%s, %s, %s, %s, 1)",
                [(compra_id, funcion_id, butaca_id, precio) for butaca_id in butaca_ids],
            )
            cursor.execute("SELECT vence_en FROM compras WHERE id = %s", (compra_id,))
            vence_en = cursor.fetchone()["vence_en"]
    except pymysql.err.IntegrityError as error:
        if error.args and error.args[0] == 1062:
            error_api(409, "BUTACA_OCUPADA", "Una o más butacas ya fueron reservadas.")
        raise

    return {
        "id": compra_id,
        "estado": "pendiente",
        "vence_en": vence_en.isoformat(),
        "subtotal_entradas": float(total),
    }


def _iso(fecha):
    return fecha.isoformat() if fecha is not None else None


def _id_desde_token_cancelacion(token):
    compra_id = leer_cancelacion(token)
    if compra_id is None:
        error_api(400, "TOKEN_INVALIDO", "El enlace de cancelación no es válido o expiró.")
    return compra_id


def _detalle_compra(compra_id, usuario_id=None):
    fila = consultar_uno(
        "SELECT c.id, c.usuario_id, c.estado, c.total, c.vence_en, c.cancelada_en, c.utilizada_en, "
        "f.fecha_hora, p.titulo, p.poster_url, s.nombre AS sala, l.nombre AS local, u.email "
        "FROM compras c "
        "JOIN funciones f ON f.id = c.funcion_id "
        "JOIN peliculas p ON p.id = f.pelicula_id "
        "JOIN salas s ON s.id = f.sala_id "
        "JOIN locales l ON l.id = s.local_id "
        "JOIN usuarios u ON u.id = c.usuario_id "
        "WHERE c.id = %s",
        (compra_id,),
    )
    if fila is None:
        error_api(404, "NO_ENCONTRADO", "La compra no existe.")
    if usuario_id is not None and fila["usuario_id"] != usuario_id:
        error_api(403, "SIN_PERMISO", "No tenés permiso sobre esta compra.")

    entradas = consultar(
        "SELECT b.fila, b.numero, e.precio FROM entradas e "
        "JOIN butacas b ON b.id = e.butaca_id "
        "WHERE e.compra_id = %s ORDER BY b.fila, b.numero",
        (compra_id,),
    )
    servicios = consultar(
        "SELECT sv.nombre, cs.cantidad, cs.precio_unitario FROM compra_servicios cs "
        "JOIN servicios sv ON sv.id = cs.servicio_id "
        "WHERE cs.compra_id = %s ORDER BY sv.nombre",
        (compra_id,),
    )
    subtotal_entradas = sum(float(entrada["precio"]) for entrada in entradas)
    return {
        "id": fila["id"],
        "estado": fila["estado"],
        "pelicula": fila["titulo"],
        "poster_url": fila["poster_url"],
        "local": fila["local"],
        "sala": fila["sala"],
        "funcion": _iso(fila["fecha_hora"]),
        "butacas": [f"{entrada['fila']}{entrada['numero']}" for entrada in entradas],
        "subtotal_entradas": subtotal_entradas,
        "servicios": [
            {
                "nombre": servicio["nombre"],
                "cantidad": servicio["cantidad"],
                "precio_unitario": float(servicio["precio_unitario"]),
                "subtotal": float(servicio["precio_unitario"]) * servicio["cantidad"],
            }
            for servicio in servicios
        ],
        "total": float(fila["total"]),
        "email": fila["email"],
        "vence_en": _iso(fila["vence_en"]) if fila["estado"] == "pendiente" else None,
        "utilizada_en": _iso(fila["utilizada_en"]),
        "cancelada_en": _iso(fila["cancelada_en"]),
        "cancelable": es_cancelable(fila["estado"], fila["fecha_hora"], fila["utilizada_en"]),
        "cancelable_hasta": _iso(cancelable_hasta(fila["fecha_hora"])),
    }


def obtener(usuario_id, compra_id):
    return _detalle_compra(compra_id, usuario_id=usuario_id)


def obtener_por_token(token):
    return _detalle_compra(_id_desde_token_cancelacion(token))


def _cancelar_compra(compra_id, usuario_id=None):
    with transaccion() as cursor:
        cursor.execute(
            "SELECT c.id, c.usuario_id, c.estado, c.utilizada_en, f.fecha_hora "
            "FROM compras c "
            "JOIN funciones f ON f.id = c.funcion_id "
            "WHERE c.id = %s FOR UPDATE",
            (compra_id,),
        )
        compra = cursor.fetchone()
        if compra is None:
            error_api(404, "NO_ENCONTRADO", "La compra no existe.")
        if usuario_id is not None and compra["usuario_id"] != usuario_id:
            error_api(403, "SIN_PERMISO", "No tenés permiso sobre esta compra.")
        if compra["estado"] == "cancelada":
            error_api(409, "YA_CANCELADA", "La compra ya fue cancelada.")
        if compra["utilizada_en"] is not None:
            error_api(409, "YA_UTILIZADA", "No se puede cancelar: la entrada ya fue utilizada.")
        if compra["estado"] != "confirmada":
            error_api(409, "COMPRA_NO_CONFIRMADA", "Solo se pueden cancelar compras confirmadas.")
        if datetime.now() >= cancelable_hasta(compra["fecha_hora"]):
            horas = current_app.config["HORAS_LIMITE_CANCELACION"]
            error_api(409, "FUERA_DE_PLAZO", f"No se puede cancelar: faltan menos de {horas} horas para la función.")

        cursor.execute(
            "UPDATE compras SET estado = 'cancelada', cancelada_en = NOW(), token_qr = NULL WHERE id = %s",
            (compra_id,),
        )
        cursor.execute("UPDATE entradas SET activa = NULL WHERE compra_id = %s AND activa = 1", (compra_id,))

    return {"id": compra_id, "estado": "cancelada"}


def cancelar(usuario_id, compra_id):
    return _cancelar_compra(compra_id, usuario_id=usuario_id)


def cancelar_por_token(datos):
    requerir_campos(datos, ("token",))
    return _cancelar_compra(_id_desde_token_cancelacion(datos["token"]))
