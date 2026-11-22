"""Helper común de filtros de listados: query params a condiciones SQL parametrizadas (SCRUM-106).

Cada listado define un mapa fijo `{parametro: (columna_sql, tipo)}`. Las columnas salen solo de ese mapa, escrito en
el código, y nunca del request; los valores del usuario van siempre como parámetros `%s`. Los parámetros que no están
en el mapa se ignoran y un valor inválido corta con 400 DATOS_INVALIDOS.

Tipos:
- "entero": id positivo (hasta 18 dígitos) → `columna = %s`.
- "dia": fecha YYYY-MM-DD → `columna >= %s AND columna < %s` (el día completo; un rango y no LIKE, así MySQL puede
  usar el índice de la columna).
- "desde" / "hasta": fecha y hora ISO YYYY-MM-DDTHH:MM:SS → `columna >= %s` / `columna <= %s`, ambos extremos
  incluidos. Si vienen los dos, `desde` no puede ser posterior a `hasta`.
"""
from datetime import date, datetime, timedelta

from src.backend.services.validaciones import datos_invalidos, entero_positivo_texto, fecha_hora_iso

MAXIMO_DIGITOS_ID = 18  # int() falla con textos larguísimos; ningún id real se acerca a este largo
# Qué hacer con un parámetro que llega vacío (?local_id=): cada listado conserva su contrato documentado.
VACIO_ES_ERROR = "error"
VACIO_SE_IGNORA = "ignorar"


def _entero(columna, texto, nombre):
    if len(texto) > MAXIMO_DIGITOS_ID:
        datos_invalidos(f"{nombre} debe ser un entero positivo.")
    return [(columna + " = %s", entero_positivo_texto(texto, nombre))]


def _dia(columna, texto, nombre):
    try:
        inicio = datetime.combine(date.fromisoformat(texto), datetime.min.time())
    except ValueError:
        datos_invalidos(f"{nombre} debe tener formato YYYY-MM-DD.")
    return [(columna + " >= %s", inicio), (columna + " < %s", inicio + timedelta(days=1))]


def _desde(columna, texto, nombre):
    return [(columna + " >= %s", fecha_hora_iso(texto, nombre))]


def _hasta(columna, texto, nombre):
    return [(columna + " <= %s", fecha_hora_iso(texto, nombre))]


TIPOS = {"entero": _entero, "dia": _dia, "desde": _desde, "hasta": _hasta}


def construir_condiciones(argumentos, filtros, vacio=VACIO_ES_ERROR):
    """Valida los filtros y devuelve `(clausulas_sql, parametros)`.

    argumentos: `request.args` o un dict con los textos recibidos (None o ausente = sin restricción).
    filtros: mapa fijo del listado, en el orden en que se agregan las condiciones.
    vacio: VACIO_ES_ERROR (un parámetro vacío da 400) o VACIO_SE_IGNORA (se toma como "sin filtro", lo que mandan
    los formularios cuando se elige "Todos").
    `clausulas_sql` son fragmentos constantes que empiezan con " AND " (texto vacío si no hay filtros), así que la
    consulta tiene que tener ya su WHERE; `parametros` es la tupla con los valores para cada `%s`, en orden.
    """
    clausulas = ""
    parametros = []
    fechas = {}
    for nombre, (columna, tipo) in filtros.items():
        texto = argumentos.get(nombre)
        if texto is None or (texto == "" and vacio == VACIO_SE_IGNORA):
            continue
        if type(texto) is not str:
            datos_invalidos(f"{nombre} tiene un valor inválido.")
        for condicion, valor in TIPOS[tipo](columna, texto, nombre):
            clausulas += " AND " + condicion
            parametros.append(valor)
        if tipo in ("desde", "hasta"):
            fechas[tipo] = (nombre, parametros[-1])
    if "desde" in fechas and "hasta" in fechas and fechas["desde"][1] > fechas["hasta"][1]:
        datos_invalidos(f"{fechas['desde'][0]} no puede ser posterior a {fechas['hasta'][0]}.")
    return clausulas, tuple(parametros)
