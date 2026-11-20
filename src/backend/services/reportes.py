"""Helper común de los reportes agregados de los dashboards (SCRUM-109).

- `construir_filtros`: valida `desde`, `hasta` y `local_id` y los convierte en condiciones SQL parametrizadas
  con el helper común de filtros (SCRUM-106).
  Las consultas que lo usan deben tener `funciones f` y `salas s` (con `s.id = f.sala_id`) en el FROM.
- `porcentaje`: `100 * parte / total` con dos decimales, sin dividir por cero.
- `punto_serie` y `total_de`: arman el formato único de las series, `{"etiqueta", "valor", "porcentaje"}`, para que
  el front dibuje todas las barras con la misma macro.
"""
from decimal import ROUND_HALF_UP, Decimal

from src.backend.filtros import construir_condiciones

DOS_DECIMALES = Decimal("0.01")
FILTROS_REPORTES = {
    "desde": ("f.fecha_hora", "desde"),
    "hasta": ("f.fecha_hora", "hasta"),
    "local_id": ("s.local_id", "entero"),
}


def construir_filtros(desde=None, hasta=None, local_id=None):
    """Valida los filtros recibidos de la URL y devuelve `(clausulas_sql, parametros)`.

    `clausulas_sql` es un texto con fragmentos constantes que empiezan con " AND " (vacío si no hay filtros) y
    `parametros` una tupla con los valores para los `%s`. `None` significa sin restricción; un texto vacío o
    inválido, o `desde` posterior a `hasta`, corta con 400 DATOS_INVALIDOS.
    """
    # Recibe los valores sueltos (y no request.args) porque el resumen también lo llama con el período anterior.
    return construir_condiciones({"desde": desde, "hasta": hasta, "local_id": local_id}, FILTROS_REPORTES)


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
