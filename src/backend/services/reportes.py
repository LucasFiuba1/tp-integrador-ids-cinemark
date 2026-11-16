"""Helper común de los reportes agregados de los dashboards (SCRUM-109).

- `construir_filtros`: valida `desde`, `hasta` y `local_id` y los convierte en condiciones SQL parametrizadas.
  Las consultas que lo usan deben tener `funciones f` y `salas s` (con `s.id = f.sala_id`) en el FROM.
- `porcentaje`: `100 * parte / total` con dos decimales, sin dividir por cero.
- `punto_serie` y `total_de`: arman el formato único de las series, `{"etiqueta", "valor", "porcentaje"}`, para que
  el front dibuje todas las barras con la misma macro.
"""
from decimal import ROUND_HALF_UP, Decimal

from src.backend.services.validaciones import datos_invalidos, entero_positivo_texto, fecha_hora_iso

MAXIMO_CARACTERES_LOCAL_ID = 18  # int() falla con textos larguísimos; ningún id real se acerca a este largo
DOS_DECIMALES = Decimal("0.01")


def _validar_local_id(valor):
    if type(valor) is not str or len(valor) > MAXIMO_CARACTERES_LOCAL_ID:
        datos_invalidos("local_id debe ser un entero positivo.")
    return entero_positivo_texto(valor, "local_id")


def construir_filtros(desde=None, hasta=None, local_id=None):
    """Valida los filtros recibidos de la URL y devuelve `(clausulas_sql, parametros)`.

    `clausulas_sql` es un texto con fragmentos constantes que empiezan con " AND " (vacío si no hay filtros) y
    `parametros` una tupla con los valores para los `%s`. `None` significa sin restricción; un texto vacío o
    inválido, o `desde` posterior a `hasta`, corta con 400 DATOS_INVALIDOS.
    """
    fecha_desde = fecha_hora_iso(desde, "desde") if desde is not None else None
    fecha_hasta = fecha_hora_iso(hasta, "hasta") if hasta is not None else None
    if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
        datos_invalidos("desde no puede ser posterior a hasta.")
    id_local = _validar_local_id(local_id) if local_id is not None else None

    clausulas = ""
    parametros = []
    if fecha_desde is not None:
        clausulas += " AND f.fecha_hora >= %s"
        parametros.append(fecha_desde)
    if fecha_hasta is not None:
        clausulas += " AND f.fecha_hora <= %s"
        parametros.append(fecha_hasta)
    if id_local is not None:
        clausulas += " AND s.local_id = %s"
        parametros.append(id_local)
    return clausulas, tuple(parametros)


def porcentaje(parte, total):
    """`100 * parte / total` redondeado a dos decimales (la mitad hacia arriba, como ROUND de MySQL).

    Con `total` en 0 o `None` (una sala sin butacas, un período sin compras) devuelve 0.0 en lugar de dividir por
    cero. Acepta int, float y Decimal (SUM de MySQL) y siempre devuelve float, listo para el JSON.
    """
    if not total:
        return 0.0
    resultado = Decimal(str(parte or 0)) * 100 / Decimal(str(total))
    return float(resultado.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP))


def total_de(filas, clave):
    """Suma `clave` en todas las filas: es el total contra el que se calcula la participación de cada una."""
    return sum(int(fila[clave]) for fila in filas)


def punto_serie(etiqueta, valor, total):
    """Un punto de una serie de barras: qué se muestra, el número y qué porcentaje de `total` representa."""
    return {"etiqueta": etiqueta, "valor": valor, "porcentaje": porcentaje(valor, total)}
