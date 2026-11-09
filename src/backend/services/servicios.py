"""ABM de servicios (comida, bebidas, estacionamiento, VIP) con baja lógica (SCRUM-71).

Los servicios valen para todas las salas. La baja pone activo = FALSE: las filas de compra_servicios ya vendidas
quedan intactas y el servicio deja de ofrecerse en GET /api/servicios.
"""
from src.backend import db
from src.backend.services.validaciones import datos_invalidos, precio_valido, texto_no_vacio

MAXIMO_DESCRIPCION = 255


def _a_json(fila):
    """Convierte el DECIMAL del precio a número y activo a booleano para devolverlos en JSON."""
    fila["precio"] = float(fila["precio"])
    fila["activo"] = bool(fila["activo"])
    return fila


def _descripcion_valida(descripcion):
    """La descripción es opcional: si falta o queda vacía se guarda NULL."""
    if descripcion is None:
        return None
    if type(descripcion) is not str:
        datos_invalidos("descripcion debe ser un texto.")
    texto = descripcion.strip()
    if len(texto) > MAXIMO_DESCRIPCION:
        datos_invalidos(f"descripcion no puede superar los {MAXIMO_DESCRIPCION} caracteres.")
    return texto or None


def validar_servicio(nombre, descripcion, precio):
    """Devuelve (nombre, descripcion, precio) limpios; los largos son los VARCHAR de schema.sql."""
    return texto_no_vacio(nombre, "nombre", 100), _descripcion_valida(descripcion), precio_valido(precio)


def listar_servicios():
    query = "SELECT id, nombre, descripcion, precio, activo FROM servicios ORDER BY nombre"
    return [_a_json(fila) for fila in db.consultar(query)]


def listar_servicios_activos():
    query = "SELECT id, nombre, descripcion, precio, activo FROM servicios WHERE activo = TRUE ORDER BY nombre"
    return [_a_json(fila) for fila in db.consultar(query)]


def obtener_servicio(servicio_id):
    query = "SELECT id, nombre, descripcion, precio, activo FROM servicios WHERE id = %s"
    fila = db.consultar_uno(query, (servicio_id,))
    return None if fila is None else _a_json(fila)


def crear_servicio(nombre, descripcion, precio):
    query = "INSERT INTO servicios (nombre, descripcion, precio) VALUES (%s, %s, %s)"
    servicio_id = db.ejecutar(query, (nombre, descripcion, precio))
    return {"id": servicio_id, "nombre": nombre, "descripcion": descripcion, "precio": float(precio), "activo": True}


def modificar_servicio(servicio_id, nombre, descripcion, precio, activo):
    """Reemplaza nombre, descripción y precio; el estado (activo) no cambia."""
    query = "UPDATE servicios SET nombre = %s, descripcion = %s, precio = %s WHERE id = %s"
    db.ejecutar(query, (nombre, descripcion, precio, servicio_id))
    return {"id": servicio_id, "nombre": nombre, "descripcion": descripcion, "precio": float(precio), "activo": activo}


def dar_de_baja_servicio(servicio_id):
    query = "UPDATE servicios SET activo = FALSE WHERE id = %s"
    db.ejecutar(query, (servicio_id,))


def reactivar_servicio(servicio_id):
    query = "UPDATE servicios SET activo = TRUE WHERE id = %s"
    db.ejecutar(query, (servicio_id,))
