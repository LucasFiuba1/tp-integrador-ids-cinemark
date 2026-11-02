from src.backend import db
from src.backend.services.validaciones import entero_en_rango, texto_no_vacio


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
    """Devuelve (nombre, filas, columnas) validados. 26 filas: una por letra (A a Z)."""
    return (
        texto_no_vacio(nombre, "nombre", 50),
        entero_en_rango(filas, "filas", 1, 26),
        entero_en_rango(columnas, "columnas", 1, 30),
    )


def letra_de_fila(indice):
    letras_filas = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return letras_filas[indice]


def generar_butacas(sala_id, filas, columnas, fil_existentes=0, col_existentes=0):
    butacas = []
    for indice_fila in range(filas):
        letra = letra_de_fila(indice_fila)
        for numero in range(1, columnas + 1):
            if indice_fila >= fil_existentes or numero > col_existentes:
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


def obtener_sala(sala_id):
    query="""
        SELECT s.id, s.local_id, l.nombre AS local, s.nombre, s.filas, s.columnas,
               s.filas * s.columnas AS capacidad
        FROM salas s
        JOIN locales l ON l.id = s.local_id
        WHERE s.id = %s AND s.activa = TRUE
    """
    res = db.consultar_uno(query, (sala_id,))
    return res


def tiene_funciones_futuras(sala_id):
    query = "SELECT id FROM funciones WHERE sala_id = %s AND activa = TRUE AND fecha_hora > NOW()"
    res = db.consultar_uno(query, (sala_id,))
    return res is not None


def eliminar_sala(sala_id):
    query = "UPDATE salas SET activa = FALSE WHERE id = %s"
    db.ejecutar(query, (sala_id,))


def hay_entradas_en_butacas_eliminadas(sala_id, filas, columnas):
    ultima_fila = letra_de_fila(filas - 1)
    query = """
        SELECT e.id FROM entradas e 
        JOIN butacas b ON b.id = e.butaca_id 
        WHERE b.sala_id = %s AND (b.fila > %s OR b.numero > %s)
    """
    res = db.consultar_uno(query, (sala_id, ultima_fila, columnas))
    return res is not None


def modificar_sala(sala_id, nombre, filas, columnas, sala_actual):
    with db.transaccion() as cursor:
        cursor.execute(
            "UPDATE salas SET nombre = %s, filas = %s, columnas = %s WHERE id = %s",
            (nombre, filas, columnas, sala_id),
        )
        cursor.execute(
            "DELETE FROM butacas WHERE sala_id = %s AND (fila > %s or numero > %s)",
            (sala_id, letra_de_fila(filas - 1), columnas),
        )
        nuevas_butacas = generar_butacas(sala_id, filas, columnas, sala_actual["filas"], sala_actual["columnas"])
        if nuevas_butacas:
            cursor.executemany(
                "INSERT INTO butacas (sala_id, fila, numero) VALUES (%s, %s, %s)",
                nuevas_butacas
            )
    return {"id": sala_id, "nombre": nombre, "capacidad": filas * columnas}