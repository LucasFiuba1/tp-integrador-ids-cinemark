"""Dashboards del backoffice: franjas horarias y cancelaciones (SCRUM-76).

Se incluye el historial de entidades con baja lógica, por eso no se filtra por `activa` en películas, salas ni funciones.
"""
from src.backend.db import consultar
from src.backend.services.filtros_dashboards import construir_filtros

HORAS_POR_FRANJA = 2
FRANJA_SQL = "FLOOR(HOUR(f.fecha_hora) / 2) * 2"

SQL_FRANJAS = (
    "SELECT " + FRANJA_SQL + " AS hora_desde, COUNT(*) AS entradas "
    "FROM entradas e "
    "JOIN compras c ON c.id = e.compra_id "
    "JOIN funciones f ON f.id = c.funcion_id "
    "JOIN salas s ON s.id = f.sala_id "
    "WHERE c.estado = 'confirmada' AND e.activa = 1"
)
SQL_FRANJAS_ORDEN = " GROUP BY " + FRANJA_SQL + " ORDER BY entradas DESC, hora_desde ASC"

COLUMNAS_CANCELACIONES = (
    "COUNT(*) AS compras, "
    "SUM(CASE WHEN c.estado = 'cancelada' THEN 1 ELSE 0 END) AS canceladas, "
    "ROUND(100 * SUM(CASE WHEN c.estado = 'cancelada' THEN 1 ELSE 0 END) / COUNT(*), 2) AS porcentaje "
)
FROM_CANCELACIONES = (
    "FROM compras c "
    "JOIN funciones f ON f.id = c.funcion_id "
    "JOIN salas s ON s.id = f.sala_id "
    "JOIN peliculas p ON p.id = f.pelicula_id "
    "WHERE c.estado IN ('confirmada', 'cancelada')"
)
SQL_CANCELACIONES_PELICULA = (
    "SELECT p.id AS pelicula_id, p.titulo AS pelicula, " + COLUMNAS_CANCELACIONES + FROM_CANCELACIONES
)
SQL_CANCELACIONES_PELICULA_ORDEN = " GROUP BY p.id, p.titulo ORDER BY canceladas DESC, p.id ASC"
SQL_CANCELACIONES_PERIODO = "SELECT DATE(f.fecha_hora) AS periodo, " + COLUMNAS_CANCELACIONES + FROM_CANCELACIONES
SQL_CANCELACIONES_PERIODO_ORDEN = " GROUP BY DATE(f.fecha_hora) ORDER BY DATE(f.fecha_hora) ASC"


def _franja_a_json(fila):
    hora_desde = int(fila["hora_desde"])
    return {
        "hora_desde": hora_desde,
        "hora_hasta": hora_desde + HORAS_POR_FRANJA,
        "entradas": int(fila["entradas"]),
    }


def _conteos_a_json(fila):
    return {
        "compras": int(fila["compras"]),
        "canceladas": int(fila["canceladas"]),
        "porcentaje": float(fila["porcentaje"]),
    }


def _por_pelicula_a_json(fila):
    return {"pelicula_id": fila["pelicula_id"], "pelicula": fila["pelicula"], **_conteos_a_json(fila)}


def _por_periodo_a_json(fila):
    return {"periodo": fila["periodo"].isoformat() + "T00:00:00", **_conteos_a_json(fila)}


def listar_franjas_horarias(desde=None, hasta=None, local_id=None):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    filas = consultar(SQL_FRANJAS + clausulas + SQL_FRANJAS_ORDEN, parametros)
    return [_franja_a_json(fila) for fila in filas]


def listar_cancelaciones(desde=None, hasta=None, local_id=None):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    por_pelicula = consultar(SQL_CANCELACIONES_PELICULA + clausulas + SQL_CANCELACIONES_PELICULA_ORDEN, parametros)
    por_periodo = consultar(SQL_CANCELACIONES_PERIODO + clausulas + SQL_CANCELACIONES_PERIODO_ORDEN, parametros)
    return {
        "por_pelicula": [_por_pelicula_a_json(fila) for fila in por_pelicula],
        "por_periodo": [_por_periodo_a_json(fila) for fila in por_periodo],
    }
