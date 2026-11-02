
"""Consultas publicas y ABM administrativo de funciones (SCRUM-56)."""
from datetime import datetime, timedelta
from decimal import Decimal

from src.backend.db import consultar, consultar_uno, transaccion
from src.backend.errores import error_api
from src.backend.services.validaciones import (datos_invalidos, entero_positivo, entero_positivo_texto, fecha_hora_iso, requerir_campos,)

MARGEN_MINUTOS = 15

COLUMNAS_ADMIN = (
    "f.id, f.pelicula_id, p.titulo AS pelicula, f.sala_id, "
    "s.nombre AS sala, s.local_id, l.nombre AS local, "
    "f.fecha_hora, f.precio, f.activa"
)
JOINS_ADMIN = (
    " FROM funciones f "
    "JOIN peliculas p ON p.id = f.pelicula_id "
    "JOIN salas s ON s.id = f.sala_id "
    "JOIN locales l ON l.id = s.local_id "
)


def obtener(funcion_id):
    """Detalle publico; se conserva para no romper la cartelera."""
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


def _a_json(fila):
    fila["fecha_hora"] = fila["fecha_hora"].isoformat()
    fila["precio"] = float(fila["precio"])
    fila["activa"] = bool(fila["activa"])
    return fila


def _precio_valido(valor):
    if type(valor) not in (int, float, Decimal):
        datos_invalidos("precio debe ser un número positivo.")
    precio = Decimal(str(valor))
    if (
        not precio.is_finite()
        or precio <= 0
        or precio > Decimal("99999999.99")
        or precio != precio.quantize(Decimal("0.01"))
    ):
        datos_invalidos("precio debe ser positivo y tener como máximo dos decimales.")
    return precio


def _validar_datos(datos, actual=None):
    campos = ("pelicula_id", "sala_id", "fecha_hora", "precio") if actual is None else ()
    requerir_campos(datos, campos)

    pelicula_id = entero_positivo(datos.get("pelicula_id", actual["pelicula_id"] if actual else None), "pelicula_id")
    sala_id = entero_positivo(datos.get("sala_id", actual["sala_id"] if actual else None), "sala_id")
    fecha = datos.get("fecha_hora", actual["fecha_hora"] if actual else None)
    fecha_hora = fecha if isinstance(fecha, datetime) else fecha_hora_iso(fecha, "fecha_hora")
    precio = _precio_valido(datos.get("precio", actual["precio"] if actual else None))

    if fecha_hora <= datetime.now():
        datos_invalidos("fecha_hora debe ser futura.")
    return pelicula_id, sala_id, fecha_hora, precio


def _validar_pelicula_sala(cursor, pelicula_id, sala_id, fecha_hora):
    # El bloqueo de la sala serializa escrituras de funciones en una misma sala.
    cursor.execute("SELECT id FROM salas WHERE id = %s AND activa = TRUE FOR UPDATE", (sala_id,))
    if cursor.fetchone() is None:
        error_api(404, "NO_ENCONTRADO", "La sala no existe o está inactiva.")

    cursor.execute(
        "SELECT duracion_min, disponible_desde, disponible_hasta "
        "FROM peliculas WHERE id = %s AND activa = TRUE",
        (pelicula_id,),
    )
    pelicula = cursor.fetchone()
    if pelicula is None:
        error_api(404, "NO_ENCONTRADO", "La película no existe o está inactiva.")
    if not pelicula["disponible_desde"] <= fecha_hora <= pelicula["disponible_hasta"]:
        datos_invalidos("fecha_hora está fuera de la disponibilidad de la película.")
    return pelicula["duracion_min"]


def _validar_solapamiento(cursor, sala_id, fecha_hora, duracion_min, funcion_id=None):
    fin_nuevo = fecha_hora + timedelta(minutes=duracion_min + MARGEN_MINUTOS)
    sql = (
        "SELECT f.id FROM funciones f "
        "JOIN peliculas p ON p.id = f.pelicula_id "
        "WHERE f.sala_id = %s AND f.activa = TRUE "
        "AND f.fecha_hora < %s "
        "AND TIMESTAMPADD(MINUTE, p.duracion_min + %s, f.fecha_hora) > %s"
    )
    parametros = [sala_id, fin_nuevo, MARGEN_MINUTOS, fecha_hora]
    if funcion_id is not None:
        sql += " AND f.id <> %s"
        parametros.append(funcion_id)
    cursor.execute(sql + " LIMIT 1", tuple(parametros))
    if cursor.fetchone() is not None:
        error_api(409, "FUNCION_SUPERPUESTA", "Ya hay una función superpuesta en esa sala.")


def _tiene_entradas(cursor, funcion_id):
    cursor.execute("SELECT id FROM entradas WHERE funcion_id = %s LIMIT 1 FOR UPDATE", (funcion_id,))
    return cursor.fetchone() is not None


def _actual(cursor, funcion_id):
    cursor.execute(
        "SELECT pelicula_id, sala_id, fecha_hora, precio FROM funciones "
        "WHERE id = %s AND activa = TRUE FOR UPDATE",
        (funcion_id,),
    )
    actual = cursor.fetchone()
    if actual is None:
        error_api(404, "NO_ENCONTRADO", "La función no existe o está inactiva.")
    return actual


def _detalle_admin(cursor, funcion_id):
    cursor.execute("SELECT " + COLUMNAS_ADMIN + JOINS_ADMIN + " WHERE f.id = %s", (funcion_id,))
    return _a_json(cursor.fetchone())


def listar(local_id=None, desde=None, hasta=None):
    sql = "SELECT " + COLUMNAS_ADMIN + JOINS_ADMIN + " WHERE 1 = 1"
    parametros = []

    if local_id not in (None, ""):
        sql += " AND s.local_id = %s"
        parametros.append(entero_positivo_texto(local_id, "local_id"))

    fecha_desde = fecha_hora_iso(desde, "desde") if desde not in (None, "") else None
    fecha_hasta = fecha_hora_iso(hasta, "hasta") if hasta not in (None, "") else None
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        datos_invalidos("desde no puede ser posterior a hasta.")
    if fecha_desde is not None:
        sql += " AND f.fecha_hora >= %s"
        parametros.append(fecha_desde)
    if fecha_hasta is not None:
        sql += " AND f.fecha_hora <= %s"
        parametros.append(fecha_hasta)

    filas = consultar(sql + " ORDER BY f.fecha_hora", tuple(parametros))
    return [_a_json(fila) for fila in filas]


def crear(datos):
    pelicula_id, sala_id, fecha_hora, precio = _validar_datos(datos)
    with transaccion() as cursor:
        duracion_min = _validar_pelicula_sala(cursor, pelicula_id, sala_id, fecha_hora)
        _validar_solapamiento(cursor, sala_id, fecha_hora, duracion_min)
        cursor.execute(
            "INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio) VALUES (%s, %s, %s, %s)",
            (pelicula_id, sala_id, fecha_hora, precio),
        )
        resultado = _detalle_admin(cursor, cursor.lastrowid)
    return resultado


def modificar(funcion_id, datos):
    with transaccion() as cursor:
        actual = _actual(cursor, funcion_id)
        pelicula_id, sala_id, fecha_hora, precio = _validar_datos(datos, actual)
        if _tiene_entradas(cursor, funcion_id) and (
            sala_id != actual["sala_id"] or fecha_hora != actual["fecha_hora"]
        ):
            error_api(409, "FUNCION_CON_ENTRADAS", "No se puede cambiar sala u horario con entradas registradas.")

        duracion_min = _validar_pelicula_sala(cursor, pelicula_id, sala_id, fecha_hora)
        _validar_solapamiento(cursor, sala_id, fecha_hora, duracion_min, funcion_id)
        cursor.execute(
            "UPDATE funciones SET pelicula_id = %s, sala_id = %s, fecha_hora = %s, precio = %s "
            "WHERE id = %s",
            (pelicula_id, sala_id, fecha_hora, precio, funcion_id),
        )
        resultado = _detalle_admin(cursor, funcion_id)
    return resultado


def dar_de_baja(funcion_id):
    with transaccion() as cursor:
        _actual(cursor, funcion_id)
        if _tiene_entradas(cursor, funcion_id):
            error_api(409, "FUNCION_CON_ENTRADAS", "No se puede eliminar una función con entradas registradas.")
        cursor.execute("UPDATE funciones SET activa = FALSE WHERE id = %s", (funcion_id,))
    return {"id": funcion_id, "baja": "logica"}
