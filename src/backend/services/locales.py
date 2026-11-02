from src.backend import db
from src.backend.services.validaciones import texto_no_vacio


def listar_locales():
    query = "SELECT id, nombre, direccion FROM locales ORDER BY nombre"
    locales = db.consultar(query)
    return locales


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


def local_tiene_salas(local_id):
    query = "SELECT id FROM salas WHERE local_id = %s"
    res = db.consultar_uno(query, (local_id,))
    return res is not None


def modificar_local(local_id, nombre_local, direccion_local):
    query = """UPDATE locales SET nombre = %s, direccion = %s WHERE id = %s"""
    db.ejecutar(query, (nombre_local, direccion_local, local_id))
    return {"id": local_id, "nombre": nombre_local, "direccion": direccion_local}


def eliminar_local(local_id):
    query = "DELETE FROM locales WHERE id=%s"
    db.ejecutar(query, (local_id, ))
