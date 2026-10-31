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