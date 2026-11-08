"""Reservas de butacas y confirmación de compra con QR y factura por email (SCRUM-62, SCRUM-66, SCRUM-67)."""
import base64

import pymysql
from flask import current_app

from src.backend.db import transaccion
from src.backend.errores import error_api
from src.backend.services import correo, perfil, qr
from src.backend.services.validaciones import entero_positivo, requerir_campos
from src.backend.tokens import firmar_qr


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


def confirmar(usuario, compra_id):
    """Confirma una compra pendiente, genera su QR y envía la factura por email (SCRUM-66, SCRUM-67).

    Si la reserva ya venció, la marca como vencida y libera las butacas antes de devolver 409 RESERVA_VENCIDA.
    El envío del email ocurre fuera de la transacción: si SMTP falla, la compra queda confirmada igual.
    """
    vencida = False
    with transaccion() as cursor:
        cursor.execute(
            "SELECT id, usuario_id, estado, total, (vence_en <= NOW()) AS vencida "
            "FROM compras WHERE id = %s FOR UPDATE",
            (compra_id,),
        )
        compra = cursor.fetchone()
        if compra is None:
            error_api(404, "NO_ENCONTRADO", "La compra no existe.")
        if compra["usuario_id"] != usuario["id"]:
            error_api(403, "SIN_PERMISO", "No tenés permiso sobre esta compra.")
        if compra["estado"] != "pendiente":
            error_api(409, "COMPRA_NO_PENDIENTE", "La compra no está pendiente de pago.")
        if compra["vencida"]:
            cursor.execute("UPDATE compras SET estado = 'vencida' WHERE id = %s", (compra_id,))
            cursor.execute("UPDATE entradas SET activa = NULL WHERE compra_id = %s AND activa = 1", (compra_id,))
            vencida = True
        else:
            token_qr = firmar_qr(compra_id)
            cursor.execute(
                "UPDATE compras SET estado = 'confirmada', confirmada_en = NOW(), token_qr = %s WHERE id = %s",
                (token_qr, compra_id),
            )
    if vencida:
        error_api(409, "RESERVA_VENCIDA", "La reserva venció y se liberaron las butacas.")

    qr_png = qr.generar_png(token_qr)
    detalle = perfil.obtener_compra(compra_id)
    cliente = {"nombre": usuario["nombre"], "email": usuario.get("email", "")}
    email_enviado = correo.enviar_factura(detalle, cliente, qr_png) if detalle is not None else False
    return {
        "id": compra_id,
        "estado": "confirmada",
        "total": float(compra["total"]),
        "qr_png_base64": base64.b64encode(qr_png).decode("ascii"),
        "email_enviado": email_enviado,
    }
