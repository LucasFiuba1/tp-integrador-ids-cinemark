from src.backend import db


def listar_locales():
    sql = "SELECT id, nombre, direccion FROM locales ORDER BY nombre"
    locales = db.consultar(sql)
    return locales

def crear_local(nombre, direccion):
    sql = "INSERT INTO locales (nombre, direccion) VALUES (%s, %s)"
    local_id = db.ejecutar(sql, (nombre, direccion))
    return {"id": local_id, "nombre": nombre, "direccion": direccion}
