from src.backend import db


def list_locals():
    query = "SELECT id, nombre, direccion FROM locales ORDER BY nombre"
    locales = db.consultar(query)
    return locales


def validate_local(nombre, direccion):
    mensaje = None
    if not nombre:
        mensaje = "El nombre es obligatorio"
    if not direccion:
        mensaje = "La direccion es obligatoria"
    return mensaje


def create_local_service(nombre, direccion):
    query = "INSERT INTO locales (nombre, direccion) VALUES (%s, %s)"
    local_id = db.ejecutar(query, (nombre, direccion))
    return {"id": local_id, "nombre": nombre, "direccion": direccion}

def delete_local_service(id):
    query = "DELETE FROM locales WHERE id=%s"
    local_borrado = db.ejecutar(query, (id, ))
    return local_borrado

def update_local_service(id, nombre, direccion):
    query = """UPDATE locales SET nombre = %s, direccion = %s WHERE id = %s"""
    db.ejecutar(query, (nombre, direccion, id))
    return {"id": id, "nombre": nombre, "direccion": direccion}