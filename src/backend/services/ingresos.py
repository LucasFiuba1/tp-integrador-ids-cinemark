"""Validación del QR de ingreso a la sala e historial de intentos (SCRUM-73, SCRUM-125)."""
from datetime import datetime, timedelta

from src.backend.db import consultar, transaccion
from src.backend.errores import error_api
from src.backend.services.validaciones import (
    entero_en_rango,
    entero_positivo,
    entero_positivo_texto,
    requerir_campos,
    texto_no_vacio,
)
from src.backend.tokens import leer_qr

LIMITE_POR_DEFECTO = 20
LIMITE_MAXIMO = 100


def _registrar_intento(cursor, compra_id, funcion_id, resultado):
    cursor.execute(
        "INSERT INTO validaciones_ingreso (compra_id, funcion_id, resultado) VALUES (%s, %s, %s)",
        (compra_id, funcion_id, resultado),
    )


def _motivo_rechazo(compra, token_qr, funcion_id):
    if compra is None or compra["token_qr"] != token_qr:
        return "QR_INVALIDO", "El código QR no corresponde a ninguna entrada.", None
    if compra["estado"] == "cancelada":
        return "CANCELADA", "La compra fue cancelada y el QR ya no es válido.", compra["id"]
    if compra["estado"] != "confirmada":
        return "QR_INVALIDO", "El código QR no corresponde a una compra confirmada.", compra["id"]
    if compra["utilizada_en"] is not None:
        usada = compra["utilizada_en"]
        return "YA_UTILIZADA", f"Este QR ya se usó el {usada:%d/%m} a las {usada:%H:%M}.", compra["id"]
    if compra["funcion_id"] != funcion_id:
        return "OTRA_FUNCION", "La entrada corresponde a otra función.", compra["id"]

    ahora = datetime.now()
    inicio = compra["fecha_hora"]
    fin = inicio + timedelta(minutes=compra["duracion_min"])
    if not compra["funcion_activa"] or inicio.date() != ahora.date() or ahora >= fin:
        return "FUERA_DE_FECHA", "La función no es de hoy o ya finalizó.", compra["id"]
    return None


def validar(datos):
    """Verifica el QR para una función, registra el intento y, si es válido, marca la compra como utilizada.

    Orden estricto de validación (SCRUM-73):
      1. Firma inválida o token inexistente -> QR_INVALIDO
      2. Compra cancelada -> CANCELADA
      3. Entrada ya usada -> YA_UTILIZADA (con fecha y hora del primer uso)
      4. Función distinta a la reservada -> OTRA_FUNCION
      5. Fecha distinta de hoy o función ya finalizada -> FUERA_DE_FECHA
    El intento se guarda dentro de la transacción antes de cortar con error_api, así el commit persiste los rechazos.
    """
    requerir_campos(datos, ("token_qr", "funcion_id"))
    token_qr = texto_no_vacio(datos["token_qr"], "token_qr", 255)
    funcion_id = entero_positivo(datos["funcion_id"], "funcion_id")

    compra_id = leer_qr(token_qr)
    rechazo = None

    with transaccion() as cursor:
        if compra_id is None:
            _registrar_intento(cursor, None, funcion_id, "qr_invalido")
            rechazo = ("QR_INVALIDO", "El código QR no es válido.")
        else:
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
            motivo = _motivo_rechazo(compra, token_qr, funcion_id)
            if motivo is not None:
                codigo, mensaje, id_registrado = motivo
                _registrar_intento(cursor, id_registrado, funcion_id, codigo.lower())
                rechazo = (codigo, mensaje)
            else:
                cursor.execute("UPDATE compras SET utilizada_en = NOW() WHERE id = %s", (compra_id,))
                _registrar_intento(cursor, compra_id, funcion_id, "valida")
                cursor.execute(
                    "SELECT b.fila, b.numero FROM entradas e "
                    "JOIN butacas b ON b.id = e.butaca_id "
                    "WHERE e.compra_id = %s ORDER BY b.fila, b.numero",
                    (compra_id,),
                )
                butacas = [f"{fila['fila']}{fila['numero']}" for fila in cursor.fetchall()]

    if rechazo is not None:
        error_api(409, *rechazo)

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


def listar(funcion_id=None, limite=None):
    """Últimos intentos de validación registrados, ordenados del más reciente al más antiguo (SCRUM-125)."""
    id_funcion = entero_positivo_texto(funcion_id, "funcion_id") if funcion_id is not None else None
    if limite is None:
        cantidad = LIMITE_POR_DEFECTO
    else:
        cantidad = entero_en_rango(entero_positivo_texto(limite, "limite"), "limite", 1, LIMITE_MAXIMO)

    condicion = "WHERE v.funcion_id = %s " if id_funcion is not None else ""
    parametros = (id_funcion, cantidad) if id_funcion is not None else (cantidad,)

    filas = consultar(
        "SELECT v.id, v.compra_id, v.funcion_id, v.resultado, v.fecha_hora, p.titulo AS pelicula, "
        "(SELECT GROUP_CONCAT(CONCAT(b.fila, b.numero) ORDER BY b.fila, b.numero SEPARATOR ', ') "
        " FROM entradas e JOIN butacas b ON b.id = e.butaca_id "
        " WHERE e.compra_id = v.compra_id) AS butacas "
        "FROM validaciones_ingreso v "
        "LEFT JOIN compras c ON c.id = v.compra_id "
        "LEFT JOIN funciones f ON f.id = COALESCE(c.funcion_id, v.funcion_id) "
        "LEFT JOIN peliculas p ON p.id = f.pelicula_id "
        f"{condicion}"
        "ORDER BY v.fecha_hora DESC, v.id DESC "
        "LIMIT %s",
        parametros,
    )
    return [
        {
            "id": fila["id"],
            "compra_id": fila["compra_id"],
            "funcion_id": fila["funcion_id"],
            "hora": fila["fecha_hora"].isoformat(),
            "pelicula": fila["pelicula"] or "—",
            "butacas": fila["butacas"] or "—",
            "resultado": fila["resultado"],
        }
        for fila in filas
    ]
