from src.backend import db
from src.backend.services.validaciones import texto_no_vacio


def listar_locales():
    query = "SELECT id, nombre, direccion FROM locales ORDER BY nombre"
    locales = db.consultar(query)
    return locales


def listar_locales_publicos():
    """Locales con al menos una sala activa, para los filtros de la cartelera (sin la dirección)."""
    query = """
        SELECT DISTINCT l.id, l.nombre
        FROM locales l
        JOIN salas s ON s.local_id = l.id AND s.activa = TRUE
        ORDER BY l.nombre
    """
    return db.consultar(query)


def validar_local(nombre_local, direccion_local):
    """Devuelve (nombre, direccion) sin espacios en los extremos; los largos son los VARCHAR de schema.sql."""
    return texto_no_vacio(nombre_local, "nombre", 100), texto_no_vacio(direccion_local, "direccion", 200)


def crear_local(nombre_local, direccion_local):
    query = "INSERT INTO locales (nombre, direccion) VALUES (%s, %s)"
    local_id = db.ejecutar(query, (nombre_local, direccion_local))
    return {"id": local_id, "nombre": nombre_local, "direccion": direccion_local}


def obtener_local(local_id):
    query = "SELECT id, nombre, direccion FROM locales WHERE id = %s"
    return db.consultar_uno(query, (local_id,))


def local_tiene_salas_activas(local_id):
    query = "SELECT id FROM salas WHERE local_id = %s AND activa = TRUE"
    res = db.consultar_uno(query, (local_id,))
    return res is not None


def local_tiene_funciones(local_id):
    """Incluye las funciones de salas dadas de baja: son historial y no se pueden borrar."""
    query = "SELECT f.id FROM funciones f JOIN salas s ON s.id = f.sala_id WHERE s.local_id = %s LIMIT 1"
    res = db.consultar_uno(query, (local_id,))
    return res is not None


def modificar_local(local_id, nombre_local, direccion_local):
    query = """UPDATE locales SET nombre = %s, direccion = %s WHERE id = %s"""
    db.ejecutar(query, (nombre_local, direccion_local, local_id))
    return {"id": local_id, "nombre": nombre_local, "direccion": direccion_local}


def eliminar_local(local_id):
    """Borra el local y sus salas dadas de baja (sin funciones); las butacas se borran en cascada."""
    with db.transaccion() as cursor:
        cursor.execute("DELETE FROM salas WHERE local_id = %s", (local_id,))
        cursor.execute("DELETE FROM locales WHERE id = %s", (local_id,))
