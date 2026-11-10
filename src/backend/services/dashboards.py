"""Dashboards del backoffice: franjas horarias y cancelaciones (SCRUM-76), ocupación y ventas por género (SCRUM-75)
y resumen de indicadores (SCRUM-124).

Se incluye el historial de entidades con baja lógica, por eso no se filtra por `activa` en películas ni salas.
Las funciones tampoco, salvo en ocupación: una función dada de baja no se ofreció, así que no suma capacidad.
"""
from datetime import datetime, timedelta

from src.backend.db import consultar
from src.backend.services.filtros_dashboards import construir_filtros
from src.backend.services.validaciones import fecha_hora_iso

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
SQL_OCUPACION_PELICULA = (
    "SELECT p.id AS pelicula_id, p.titulo AS pelicula, "
    + VENDIDAS_PELICULA_SQL + " AS vendidas, "
    "SUM(" + CAPACIDAD_SQL + ") AS capacidad, "
    "ROUND(100 * " + VENDIDAS_PELICULA_SQL + " / SUM(" + CAPACIDAD_SQL + "), 2) AS ocupacion "
    + FROM_OCUPACION
)
SQL_OCUPACION_PELICULA_ORDEN = " GROUP BY p.id, p.titulo ORDER BY ocupacion DESC, p.id ASC"
SQL_OCUPACION_FUNCION = (
    "SELECT f.id AS funcion_id, p.titulo AS pelicula, l.nombre AS local, s.nombre AS sala, f.fecha_hora, "
    + VENDIDAS_FUNCION_SQL + " AS vendidas, "
    + CAPACIDAD_SQL + " AS capacidad, "
    "ROUND(100 * " + VENDIDAS_FUNCION_SQL + " / (" + CAPACIDAD_SQL + "), 2) AS ocupacion "
    + FROM_OCUPACION
)
SQL_OCUPACION_FUNCION_ORDEN = " ORDER BY ocupacion DESC, f.fecha_hora ASC, f.id ASC"

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

# Resumen: `compras.total` incluye los servicios, así que no se puede unir `entradas` directo o se repetiría por cada
# entrada de la compra. Por eso las entradas se cuentan aparte, en una subconsulta por compra.
SQL_RESUMEN_VENTAS = (
    "SELECT COALESCE(SUM(v.entradas), 0) AS entradas, COALESCE(SUM(c.total), 0) AS ingresos "
    "FROM compras c "
    "JOIN funciones f ON f.id = c.funcion_id "
    "JOIN salas s ON s.id = f.sala_id "
    "LEFT JOIN (SELECT compra_id, COUNT(*) AS entradas FROM entradas WHERE activa = 1 GROUP BY compra_id) v "
    "ON v.compra_id = c.id "
    "WHERE c.estado = 'confirmada'"
)
SQL_RESUMEN_OCUPACION = (
    "SELECT ROUND(100 * " + VENDIDAS_PELICULA_SQL + " / SUM(" + CAPACIDAD_SQL + "), 2) AS ocupacion "
    + FROM_OCUPACION
)
SQL_RESUMEN_CANCELACIONES = "SELECT " + COLUMNAS_CANCELACIONES + FROM_CANCELACIONES
PRIMERA_FECHA_MYSQL = datetime(1000, 1, 1)  # DATETIME no admite fechas anteriores


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


def _ocupacion_a_json(fila):
    return {
        "vendidas": int(fila["vendidas"]),
        "capacidad": int(fila["capacidad"]),
        "ocupacion": float(fila["ocupacion"]),
    }


def _ocupacion_pelicula_a_json(fila):
    return {"pelicula_id": fila["pelicula_id"], "pelicula": fila["pelicula"], **_ocupacion_a_json(fila)}


def _ocupacion_funcion_a_json(fila):
    return {
        "funcion_id": fila["funcion_id"],
        "pelicula": fila["pelicula"],
        "local": fila["local"],
        "sala": fila["sala"],
        "fecha_hora": fila["fecha_hora"].isoformat(),
        **_ocupacion_a_json(fila),
    }


def _venta_genero_a_json(fila):
    return {"genero": fila["genero"], "entradas": int(fila["entradas"]), "monto": float(fila["monto"])}


def _decimal_o_none(valor):
    """Sin funciones o sin compras en el período, la división de MySQL da NULL: se manda null, no 0."""
    return None if valor is None else float(valor)


def _indicadores_periodo(desde, hasta, local_id):
    clausulas, parametros = construir_filtros(desde, hasta, local_id)
    ventas = consultar(SQL_RESUMEN_VENTAS + clausulas, parametros)[0]
    ocupacion = consultar(SQL_RESUMEN_OCUPACION + clausulas, parametros)[0]
    cancelaciones = consultar(SQL_RESUMEN_CANCELACIONES + clausulas, parametros)[0]
    return {
        "entradas": int(ventas["entradas"]),
        "ingresos": float(ventas["ingresos"]),
        "ocupacion": _decimal_o_none(ocupacion["ocupacion"]),
        "cancelaciones": _decimal_o_none(cancelaciones["porcentaje"]),
    }


def _periodo_anterior(desde, hasta):
    """Devuelve `(desde, hasta)` del período de igual duración que termina un segundo antes de `desde`.

    Sin un período completo o sin fechas válidas para MySQL antes de `desde`, no hay con qué comparar: None.
    Se llama con los filtros ya validados.
    """
    if desde is None or hasta is None:
        return None
    inicio = fecha_hora_iso(desde, "desde")
    duracion = fecha_hora_iso(hasta, "hasta") - inicio
    if inicio - PRIMERA_FECHA_MYSQL <= duracion:
        return None
    fin_anterior = inicio - timedelta(seconds=1)
    return (fin_anterior - duracion).isoformat(), fin_anterior.isoformat()


def _variacion_porcentual(valor, anterior):
    if valor is None or not anterior:  # con 0 en el período anterior no hay porcentaje posible
        return None
    return round((valor - anterior) / anterior * 100, 2)


def _variacion_en_puntos(valor, anterior):
    if valor is None or anterior is None:
        return None
    return round(valor - anterior, 2)


VARIACIONES_RESUMEN = (
    ("entradas", _variacion_porcentual),
    ("ingresos", _variacion_porcentual),
    ("ocupacion", _variacion_en_puntos),
    ("cancelaciones", _variacion_en_puntos),
)


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
    return [_venta_genero_a_json(fila) for fila in filas]


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


def resumen_dashboard(desde=None, hasta=None, local_id=None):
    actual = _indicadores_periodo(desde, hasta, local_id)  # valida los filtros antes de calcular el período anterior
    periodo = _periodo_anterior(desde, hasta)
    anterior = _indicadores_periodo(periodo[0], periodo[1], local_id) if periodo else {}
    return {
        clave: {
            "valor": actual[clave],
            "anterior": anterior.get(clave),
            "variacion": variacion(actual[clave], anterior.get(clave)),
        }
        for clave, variacion in VARIACIONES_RESUMEN
    }
