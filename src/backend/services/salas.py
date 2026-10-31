from src.backend import db


def listar_salas(local_id=None):
    query = """
        SELECT s.id, s.local_id, l.nombre AS local, s.nombre, s.filas, s.columnas, 
               s.filas * s.columnas AS capacidad
        FROM salas s
        JOIN locales l ON l.id = s.local_id
        WHERE s.activa = TRUE AND (%s IS NULL OR s.local_id = %s)
        ORDER BY l.nombre, s.nombre
    """
    res = db.consultar(query, (local_id, local_id))
    return res

def validar_salas(nombre, filas, columnas):
    max_filas = 26
    max_columnas = 30
    mensaje = None
    if not nombre:
        mensaje = "El nombre es obligatorio."
    elif not isinstance(filas, int) or filas < 1 or filas > max_filas:
        mensaje = "La cantidad de filas debe ser un número entero entre 1 y 26."
    elif not isinstance(columnas, int) or columnas < 1 or columnas > max_columnas:
        mensaje = "La cantidad de columnas debe ser un número entero entre 1 y 30."
    return mensaje


def generar_butacas(sala_id, filas, columnas):
    butacas = []
    letras_filas = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for indice_fila in range(filas):
        letra = letras_filas[indice_fila]
        for numero in range(1, columnas + 1):
            butacas.append((sala_id, letra, numero))
    return butacas


def crear_sala(local_id, nombre, filas, columnas):
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO salas (local_id, nombre, filas, columnas) VALUES (%s, %s, %s, %s)",
            (local_id, nombre, filas, columnas),
        )
        sala_id = cursor.lastrowid
        butacas = generar_butacas(sala_id, filas, columnas)
        cursor.executemany(
            "INSERT INTO butacas (sala_id, fila, numero) VALUES (%s, %s, %s)",
            butacas,
        )
    return {"id": sala_id, "nombre": nombre, "capacidad": filas * columnas}