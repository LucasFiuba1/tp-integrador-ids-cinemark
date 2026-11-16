"""Dashboards del backoffice: franjas horarias y cancelaciones (SCRUM-76), ocupación y ventas por género (SCRUM-75).

Se incluye el historial de entidades con baja lógica, por eso no se filtra por `activa` en películas ni salas.
Las funciones tampoco, salvo en ocupación: una función dada de baja no se ofreció, así que no suma capacidad.
"""
from src.backend.db import consultar
from src.backend.services.reportes import construir_filtros, porcentaje, punto_serie, total_de

HORAS_POR_FRANJA = 2
FRANJA_SQL = "FLOOR(HOUR(f.fecha_hora) / 2) * 2"
ENTRADA_VENDIDA = "c.estado = 'confirmada' AND e.activa = 1"

SQL_FRANJAS = (
    "SELECT " + FRANJA_SQL + " AS hora_desde, COUNT(*) AS entradas "
    "FROM entradas e "
    "JOIN compras c ON c.id = e.compra_id "
    "JOIN funciones f ON f.id = c.funcion_id "
    "JOIN salas s ON s.id = f.sala_id "
    "WHERE " + ENTRADA_VENDIDA
)
SQL_FRANJAS_ORDEN = " GROUP BY " + FRANJA_SQL + " ORDER BY entradas DESC, hora_desde ASC"

# Se parte de `funciones` para que las que no vendieron sumen capacidad. Las vendidas se cuentan en una subconsulta:
# con un LEFT JOIN directo a `entradas`, la capacidad de la sala se sumaría una vez por cada entrada.
FROM_OCUPACION = (
    "FROM funciones f "
    "JOIN salas s ON s.id = f.sala_id "
    "JOIN locales l ON l.id = s.local_id "
    "JOIN peliculas p ON p.id = f.pelicula_id "
    "LEFT JOIN (SELECT e.funcion_id, COUNT(*) AS vendidas "
    "FROM entradas e JOIN compras c ON c.id = e.compra_id "
    "WHERE " + ENTRADA_VENDIDA + " GROUP BY e.funcion_id) v ON v.funcion_id = f.id "
    "WHERE f.activa = 1"
)
CAPACIDAD_SQL = "s.filas * s.columnas"
VENDIDAS_PELICULA_SQL = "COALESCE(SUM(v.vendidas), 0)"
VENDIDAS_FUNCION_SQL = "COALESCE(v.vendidas, 0)"
# El porcentaje de ocupación se calcula en Python con `reportes.porcentaje` (sin división por cero); el SQL solo
# ordena por la misma cuenta, redondeada igual para que los empates se desempaten como dice docs/endpoints.md.
SQL_OCUPACION_PELICULA = (
    "SELECT p.id AS pelicula_id, p.titulo AS pelicula, "
    + VENDIDAS_PELICULA_SQL + " AS vendidas, "
    "SUM(" + CAPACIDAD_SQL + ") AS capacidad "
    + FROM_OCUPACION
)
SQL_OCUPACION_PELICULA_ORDEN = (
    " GROUP BY p.id, p.titulo "
    "ORDER BY ROUND(100 * " + VENDIDAS_PELICULA_SQL + " / SUM(" + CAPACIDAD_SQL + "), 2) DESC, p.id ASC"
)
SQL_OCUPACION_FUNCION = (
    "SELECT f.id AS funcion_id, p.titulo AS pelicula, l.nombre AS local, s.nombre AS sala, f.fecha_hora, "
    + VENDIDAS_FUNCION_SQL + " AS vendidas, "
    + CAPACIDAD_SQL + " AS capacidad "
    + FROM_OCUPACION
)
SQL_OCUPACION_FUNCION_ORDEN = (
    " ORDER BY ROUND(100 * " + VENDIDAS_FUNCION_SQL + " / (" + CAPACIDAD_SQL + "), 2) DESC, "
    "f.fecha_hora ASC, f.id ASC"
)

# `peliculas.genero` guarda varios géneros separados por coma: cada venta se cuenta en el primero (el principal),
# así la suma de todas las filas coincide con el total vendido.
GENERO_SQL = "SUBSTRING_INDEX(p.genero, ',', 1)"
# El monto es el precio de cada entrada: `compras.total` incluye servicios y se repetiría por cada entrada.
SQL_VENTAS_GENERO = (
    "SELECT " + GENERO_SQL + " AS genero, COUNT(*) AS entradas, SUM(e.precio) AS monto "
    "FROM entradas e "
    "JOIN compras c ON c.id = e.compra_id "
    "JOIN funciones f ON f.id = c.funcion_id "
    "JOIN salas s ON s.id = f.sala_id "
    "JOIN peliculas p ON p.id = f.pelicula_id "
    "WHERE " + ENTRADA_VENDIDA
)
SQL_VENTAS_GENERO_ORDEN = " GROUP BY " + GENERO_SQL + " ORDER BY entradas DESC, genero ASC"

COLUMNAS_CANCELACIONES = (
    "COUNT(*) AS compras, "
    "SUM(CASE WHEN c.estado = 'cancelada' THEN 1 ELSE 0 END) AS canceladas "
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


# Cada fila de una serie lleva, además de sus campos propios, `etiqueta`, `valor` y `porcentaje` (reportes.py).
def _franja_a_json(fila, total):
    hora_desde = int(fila["hora_desde"])
    hora_hasta = hora_desde + HORAS_POR_FRANJA
    entradas = int(fila["entradas"])
    return {
        "hora_desde": hora_desde,
        "hora_hasta": hora_hasta,
        "entradas": entradas,
        **punto_serie(f"{hora_desde} a {hora_hasta} h", entradas, total),
    }


def _conteos_a_json(fila, etiqueta):
    """Cancelaciones: el valor son las canceladas y el porcentaje, sobre las compras de esa misma fila."""
    compras = int(fila["compras"])
    canceladas = int(fila["canceladas"])
    return {"compras": compras, "canceladas": canceladas, **punto_serie(etiqueta, canceladas, compras)}


def _por_pelicula_a_json(fila):
    return {"pelicula_id": fila["pelicula_id"], "pelicula": fila["pelicula"],
            **_conteos_a_json(fila, fila["pelicula"])}


def _por_periodo_a_json(fila):
    periodo = fila["periodo"].isoformat() + "T00:00:00"
    return {"periodo": periodo, **_conteos_a_json(fila, periodo)}


def _ocupacion_a_json(fila, etiqueta):
    """Ocupación: el valor son las butacas vendidas y el porcentaje, sobre la capacidad de esa misma fila."""
    vendidas = int(fila["vendidas"])
    capacidad = int(fila["capacidad"])
    return {
        "vendidas": vendidas,
        "capacidad": capacidad,
        "ocupacion": porcentaje(vendidas, capacidad),
        **punto_serie(etiqueta, vendidas, capacidad),
    }


def _ocupacion_pelicula_a_json(fila):
    return {"pelicula_id": fila["pelicula_id"], "pelicula": fila["pelicula"],
            **_ocupacion_a_json(fila, fila["pelicula"])}


def _ocupacion_funcion_a_json(fila):
    return {
        "funcion_id": fila["funcion_id"],
        "pelicula": fila["pelicula"],
        "local": fila["local"],
        "sala": fila["sala"],
        "fecha_hora": fila["fecha_hora"].isoformat(),
        **_ocupacion_a_json(fila, f"{fila['pelicula']} ({fila['local']}, {fila['sala']})"),
    }


def _venta_genero_a_json(fila, total):
    """Ventas por género: el porcentaje es la participación del género sobre el total de entradas vendidas."""
    entradas = int(fila["entradas"])
    return {
        "genero": fila["genero"],
        "entradas": entradas,
        "monto": float(fila["monto"]),
        **punto_serie(fila["genero"], entradas, total),
    }


def listar_ocupacion(desde=None, hasta=None, local_id=None):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    por_pelicula = consultar(SQL_OCUPACION_PELICULA + clausulas + SQL_OCUPACION_PELICULA_ORDEN, parametros)
    por_funcion = consultar(SQL_OCUPACION_FUNCION + clausulas + SQL_OCUPACION_FUNCION_ORDEN, parametros)
    return {
        "por_pelicula": [_ocupacion_pelicula_a_json(fila) for fila in por_pelicula],
        "por_funcion": [_ocupacion_funcion_a_json(fila) for fila in por_funcion],
    }


def listar_ventas_genero(desde=None, hasta=None, local_id=None):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    filas = consultar(SQL_VENTAS_GENERO + clausulas + SQL_VENTAS_GENERO_ORDEN, parametros)
    total = total_de(filas, "entradas")
    return [_venta_genero_a_json(fila, total) for fila in filas]


def listar_franjas_horarias(desde=None, hasta=None, local_id=None):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    filas = consultar(SQL_FRANJAS + clausulas + SQL_FRANJAS_ORDEN, parametros)
    total = total_de(filas, "entradas")
    return [_franja_a_json(fila, total) for fila in filas]


def listar_cancelaciones(desde=None, hasta=None, local_id=None):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    por_pelicula = consultar(SQL_CANCELACIONES_PELICULA + clausulas + SQL_CANCELACIONES_PELICULA_ORDEN, parametros)
    por_periodo = consultar(SQL_CANCELACIONES_PERIODO + clausulas + SQL_CANCELACIONES_PERIODO_ORDEN, parametros)
    return {
        "por_pelicula": [_por_pelicula_a_json(fila) for fila in por_pelicula],
        "por_periodo": [_por_periodo_a_json(fila) for fila in por_periodo],
    }
