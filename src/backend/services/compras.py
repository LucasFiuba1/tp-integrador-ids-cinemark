"""Reservas de butacas, servicios de la compra, confirmación con QR y factura por email, detalle y cancelación de
compras (SCRUM-62, SCRUM-64, SCRUM-66, SCRUM-67, SCRUM-69, SCRUM-70)."""
import base64
from datetime import datetime

import pymysql
from flask import current_app

from src.backend.db import consultar, consultar_uno, marcadores, transaccion
from src.backend.errores import error_api
from src.backend.services import correo, perfil, qr
from src.backend.services.perfil import cancelable_hasta, es_cancelable
from src.backend.services.validaciones import datos_invalidos, entero_en_rango, entero_positivo, requerir_campos
from src.backend.tokens import firmar_qr, leer_cancelacion

MAXIMO_CANTIDAD_SERVICIO = 20  # por servicio y por compra; evita pedidos absurdos (la columna admite hasta 65535)
MAXIMO_SERVICIOS_POR_COMPRA = 50  # servicios distintos en un mismo pedido; acota el IN (...) de la consulta


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

            cursor.execute(
                "SELECT id FROM butacas WHERE sala_id = %s AND id IN (" + marcadores(len(butaca_ids)) + ")",
                (funcion["sala_id"], *butaca_ids),
            )
            butacas_validas = {fila["id"] for fila in cursor.fetchall()}
            if butacas_validas != set(butaca_ids):
                error_api(400, "DATOS_INVALIDOS", "Una o más butacas no pertenecen a la sala.")
            cursor.execute(
                "SELECT b.fila, b.numero FROM entradas e "
                "JOIN butacas b ON b.id = e.butaca_id "
                "WHERE e.funcion_id = %s AND e.activa = 1 AND e.butaca_id IN (" + marcadores(len(butaca_ids)) + ") "
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


def _estado_informado(fila):
    """Una pendiente cuyo plazo ya pasó se informa como vencida aunque la base todavía no se haya actualizado."""
    return "vencida" if fila["estado"] == "pendiente" and fila["vencida"] else fila["estado"]


def _qr_base64(estado, token_qr):
    if estado != "confirmada" or not token_qr:
        return None
    return base64.b64encode(qr.generar_qr(token_qr)).decode("ascii")


def _detalle_compra(compra_id, usuario_id=None):
    """Detalle de una compra. Con usuario_id exige que sea suya (403 si no); sin él, no filtra por dueño."""
    fila = consultar_uno(
        "SELECT c.id, c.usuario_id, c.estado, c.total, c.vence_en, c.cancelada_en, c.utilizada_en, c.token_qr, "
        "(c.vence_en <= NOW()) AS vencida, "
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
        "SELECT cs.servicio_id, sv.nombre, cs.cantidad, cs.precio_unitario FROM compra_servicios cs "
        "JOIN servicios sv ON sv.id = cs.servicio_id "
        "WHERE cs.compra_id = %s ORDER BY sv.nombre",
        (compra_id,),
    )
    subtotal_entradas = sum(float(entrada["precio"]) for entrada in entradas)
    estado = _estado_informado(fila)
    return {
        "id": fila["id"],
        "estado": estado,
        "pelicula": fila["titulo"],
        "poster_url": fila["poster_url"],
        "local": fila["local"],
        "sala": fila["sala"],
        "funcion": _iso(fila["fecha_hora"]),
        "butacas": [f"{entrada['fila']}{entrada['numero']}" for entrada in entradas],
        "subtotal_entradas": subtotal_entradas,
        "servicios": [
            {
                "servicio_id": servicio["servicio_id"],
                "nombre": servicio["nombre"],
                "cantidad": servicio["cantidad"],
                "precio_unitario": float(servicio["precio_unitario"]),
                "subtotal": float(servicio["precio_unitario"]) * servicio["cantidad"],
            }
            for servicio in servicios
        ],
        "total": float(fila["total"]),
        "email": fila["email"],
        "vence_en": _iso(fila["vence_en"]) if estado == "pendiente" else None,
        "utilizada_en": _iso(fila["utilizada_en"]),
        "cancelada_en": _iso(fila["cancelada_en"]),
        "cancelable": es_cancelable(estado, fila["fecha_hora"], fila["utilizada_en"]),
        "cancelable_hasta": _iso(cancelable_hasta(fila["fecha_hora"])),
        "qr_png_base64": _qr_base64(estado, fila["token_qr"]),
    }


def obtener(usuario, compra_id):
    """El cliente solo ve sus compras; el admin puede ver cualquiera."""
    return _detalle_compra(compra_id, usuario_id=None if usuario["rol"] == "admin" else usuario["id"])


def obtener_por_token(token):
    return _detalle_compra(_id_desde_token_cancelacion(token))


def _cancelar_compra(compra_id, usuario_id=None):
    with transaccion() as cursor:
        cursor.execute(
            "SELECT c.id, c.usuario_id, c.estado, c.utilizada_en, f.fecha_hora, u.nombre, u.email "
            "FROM compras c "
            "JOIN funciones f ON f.id = c.funcion_id "
            "JOIN usuarios u ON u.id = c.usuario_id "
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

    detalle = perfil.obtener_compra(compra_id)
    if detalle is not None:
        correo.enviar_cancelacion(detalle,{"nombre": compra["nombre"], "email": compra["email"]},)

    return {"id": compra_id, "estado": "cancelada"}


def cancelar(usuario_id, compra_id):
    return _cancelar_compra(compra_id, usuario_id=usuario_id)


def cancelar_por_token(datos):
    requerir_campos(datos, ("token",))
    return _cancelar_compra(_id_desde_token_cancelacion(datos["token"]))


def _bloquear_compra_pendiente(cursor, compra_id, usuario_id):
    """Bloquea la compra (FOR UPDATE) y verifica que exista, sea del usuario y esté pendiente.

    Devuelve True si la reserva ya venció: en ese caso la marca vencida y libera sus butacas. Quien llama devuelve el
    409 con `_reserva_vencida()` después de la transacción, porque `error_api` dentro de ella desharía esos cambios.
    """
    cursor.execute(
        "SELECT id, usuario_id, estado, total, (vence_en <= NOW()) AS vencida "
        "FROM compras WHERE id = %s FOR UPDATE",
        (compra_id,),
    )
    compra = cursor.fetchone()
    if compra is None:
        error_api(404, "NO_ENCONTRADO", "La compra no existe.")
    if compra["usuario_id"] != usuario_id:
        error_api(403, "SIN_PERMISO", "No tenés permiso sobre esta compra.")
    if compra["estado"] != "pendiente":
        error_api(409, "COMPRA_NO_PENDIENTE", "La compra no está pendiente de pago.")
    if not compra["vencida"]:
        return False
    cursor.execute("UPDATE compras SET estado = 'vencida' WHERE id = %s", (compra_id,))
    cursor.execute("UPDATE entradas SET activa = NULL WHERE compra_id = %s AND activa = 1", (compra_id,))
    return True


def _reserva_vencida():
    error_api(409, "RESERVA_VENCIDA", "La reserva venció y se liberaron las butacas.")


def _total_compra(cursor, compra_id):
    """Entradas activas más servicios de la compra, con los precios guardados en ella (no los vigentes)."""
    cursor.execute("SELECT precio FROM entradas WHERE compra_id = %s AND activa = 1", (compra_id,))
    entradas = cursor.fetchall()
    cursor.execute("SELECT cantidad, precio_unitario FROM compra_servicios WHERE compra_id = %s", (compra_id,))
    servicios = cursor.fetchall()
    total = sum(entrada["precio"] for entrada in entradas)
    return total + sum(servicio["cantidad"] * servicio["precio_unitario"] for servicio in servicios)


def _servicios_pedidos(datos):
    """Valida el cuerpo `[{servicio_id, cantidad}]` y devuelve {servicio_id: cantidad}. La lista vacía es válida:
    quita todos los servicios de la compra ("Continuar sin servicios")."""
    if type(datos) is not list:
        datos_invalidos("El cuerpo debe ser una lista de servicios.")
    if len(datos) > MAXIMO_SERVICIOS_POR_COMPRA:
        datos_invalidos(f"No se pueden pedir más de {MAXIMO_SERVICIOS_POR_COMPRA} servicios distintos.")
    pedidos = {}
    for item in datos:
        requerir_campos(item, ("servicio_id", "cantidad"))
        servicio_id = entero_positivo(item["servicio_id"], "servicio_id")
        if servicio_id in pedidos:  # la PK (compra_id, servicio_id) haría fallar el INSERT con un 500
            datos_invalidos("No repitas un servicio en la lista.")
        pedidos[servicio_id] = entero_en_rango(item["cantidad"], "cantidad", 1, MAXIMO_CANTIDAD_SERVICIO)
    return pedidos


def definir_servicios(usuario_id, compra_id, datos):
    """Reemplaza los servicios de una compra pendiente y recalcula su total (SCRUM-64).

    Cada servicio guarda en `compra_servicios` su precio vigente en este momento: si el admin lo edita después, la
    compra conserva el precio con el que se eligió.
    """
    pedidos = _servicios_pedidos(datos)
    with transaccion() as cursor:
        vencida = _bloquear_compra_pendiente(cursor, compra_id, usuario_id)
        if not vencida:
            precios = {}
            if pedidos:
                cursor.execute(
                    "SELECT id, precio FROM servicios WHERE activo = TRUE AND id IN (" + marcadores(len(pedidos)) + ")",
                    tuple(pedidos),
                )
                precios = {fila["id"]: fila["precio"] for fila in cursor.fetchall()}
            if set(precios) != set(pedidos):
                datos_invalidos("Uno o más servicios no existen o no están disponibles.")
            cursor.execute("DELETE FROM compra_servicios WHERE compra_id = %s", (compra_id,))
            if pedidos:
                cursor.executemany(
                    "INSERT INTO compra_servicios (compra_id, servicio_id, cantidad, precio_unitario) "
                    "VALUES (%s, %s, %s, %s)",
                    [(compra_id, servicio_id, cantidad, precios[servicio_id])
                     for servicio_id, cantidad in pedidos.items()],
                )
            total = _total_compra(cursor, compra_id)
            cursor.execute("UPDATE compras SET total = %s WHERE id = %s", (total, compra_id))

    if vencida:
        _reserva_vencida()
    return {"id": compra_id, "total": float(total)}


def confirmar(usuario, compra_id):
    """Confirma una compra pendiente, genera su QR y envía la factura por email (SCRUM-66, SCRUM-67).

    Si la reserva ya venció, la marca como vencida y libera las butacas antes de devolver 409 RESERVA_VENCIDA.
    El envío del email ocurre fuera de la transacción: si SMTP falla, la compra queda confirmada igual.
    """
    with transaccion() as cursor:
        vencida = _bloquear_compra_pendiente(cursor, compra_id, usuario["id"])
        if not vencida:
            token_qr = firmar_qr(compra_id)
            total = _total_compra(cursor, compra_id)
            cursor.execute(
                "UPDATE compras SET estado = 'confirmada', confirmada_en = NOW(), token_qr = %s, total = %s "
                "WHERE id = %s",
                (token_qr, total, compra_id),
            )

    if vencida:
        _reserva_vencida()

    qr_png = qr.generar_qr(token_qr)
    detalle = perfil.obtener_compra(compra_id)
    cliente = {"nombre": usuario["nombre"], "email": usuario.get("email", "")}
    email_enviado = correo.enviar_factura(detalle, cliente, qr_png) if detalle is not None else False
    return {
        "id": compra_id,
        "estado": "confirmada",
        "total": float(total),
        "qr_png_base64": base64.b64encode(qr_png).decode("ascii"),
        "email_enviado": email_enviado,
    }
