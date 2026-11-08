"""Validación del QR de ingreso a la sala (SCRUM-73)."""
from datetime import datetime, timedelta

from src.backend.db import transaccion
from src.backend.errores import error_api
from src.backend.services.validaciones import entero_positivo, requerir_campos, texto_no_vacio
from src.backend.tokens import leer_qr


def validar(datos):
    """Verifica el QR para una función y, si es válido, marca la compra como utilizada con bloqueo de fila.

    Orden estricto de validación (SCRUM-73):
      1. Firma inválida o token inexistente -> QR_INVALIDO
      2. Compra cancelada -> CANCELADA
      3. Entrada ya usada -> YA_UTILIZADA (con fecha y hora del primer uso)
      4. Función distinta a la reservada -> OTRA_FUNCION
      5. Fecha distinta de hoy o función ya finalizada -> FUERA_DE_FECHA
    """
    requerir_campos(datos, ("token_qr", "funcion_id"))
    token_qr = texto_no_vacio(datos["token_qr"], "token_qr", 255)
    funcion_id = entero_positivo(datos["funcion_id"], "funcion_id")

    compra_id = leer_qr(token_qr)
    if compra_id is None:
        error_api(409, "QR_INVALIDO", "El código QR no es válido.")

    with transaccion() as cursor:
        cursor.execute(
            "SELECT c.id, c.funcion_id, c.estado, c.token_qr, c.utilizada_en, "
            "f.fecha_hora, f.activa AS funcion_activa, p.titulo AS pelicula, p.duracion_min, "
            "s.nombre AS sala, l.nombre AS local, u.nombre AS titular "
            "FROM compras c "
            "JOIN funciones f ON f.id = c.funcion_id "
            "JOIN peliculas p ON p.id = f.pelicula_id "
            "JOIN salas s ON s.id = f.sala_id "
            "JOIN locales l ON l.id = s.local_id "
            "JOIN usuarios u ON u.id = c.usuario_id "
            "WHERE c.id = %s FOR UPDATE",
            (compra_id,),
        )
        compra = cursor.fetchone()
        if compra is None or compra["token_qr"] != token_qr:
            error_api(409, "QR_INVALIDO", "El código QR no corresponde a ninguna entrada.")
        if compra["estado"] == "cancelada":
            error_api(409, "CANCELADA", "La compra fue cancelada y el QR ya no es válido.")
        if compra["estado"] != "confirmada":
            error_api(409, "QR_INVALIDO", "El código QR no corresponde a una compra confirmada.")
        if compra["utilizada_en"] is not None:
            usada = compra["utilizada_en"]
            error_api(409, "YA_UTILIZADA", f"Este QR ya se usó el {usada:%d/%m} a las {usada:%H:%M}.")
        if compra["funcion_id"] != funcion_id:
            error_api(409, "OTRA_FUNCION", "La entrada corresponde a otra función.")

        ahora = datetime.now()
        inicio = compra["fecha_hora"]
        fin = inicio + timedelta(minutes=compra["duracion_min"])
        if not compra["funcion_activa"] or inicio.date() != ahora.date() or ahora >= fin:
            error_api(409, "FUERA_DE_FECHA", "La función no es de hoy o ya finalizó.")

        cursor.execute("UPDATE compras SET utilizada_en = NOW() WHERE id = %s", (compra_id,))
        cursor.execute(
            "SELECT b.fila, b.numero FROM entradas e "
            "JOIN butacas b ON b.id = e.butaca_id "
            "WHERE e.compra_id = %s ORDER BY b.fila, b.numero",
            (compra_id,),
        )
        butacas = [f"{fila['fila']}{fila['numero']}" for fila in cursor.fetchall()]

    return {
        "valido": True,
        "compra_id": compra["id"],
        "butacas": butacas,
        "pelicula": compra["pelicula"],
        "funcion": compra["fecha_hora"].isoformat(),
        "local": compra["local"],
        "sala": compra["sala"],
        "titular": compra["titular"],
    }
