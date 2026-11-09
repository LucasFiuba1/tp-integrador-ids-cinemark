"""Filtros opcionales (desde, hasta, local_id) compartidos por los dashboards (SCRUM-76).

Las consultas que los usan deben tener `funciones f` y `salas s` (con `s.id = f.sala_id`) en el FROM.
"""
from src.backend.services.validaciones import datos_invalidos, entero_positivo_texto, fecha_hora_iso

MAXIMO_CARACTERES_LOCAL_ID = 18  # int() falla con textos larguísimos; ningún id real se acerca a este largo


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
