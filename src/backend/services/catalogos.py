"""Catálogos públicos usados por los filtros de la cartelera."""

from datetime import datetime

from src.backend.db import consultar
from src.backend.services.cartelera import FUNCIONES_VIGENTES


SQL_GENEROS = (
    "SELECT DISTINCT peliculas.genero AS valor"
    + FUNCIONES_VIGENTES
    + " ORDER BY peliculas.genero"
)

SQL_CLASIFICACIONES = (
    "SELECT DISTINCT peliculas.clasificacion AS valor"
    + FUNCIONES_VIGENTES
    + " AND peliculas.clasificacion IS NOT NULL "
    "AND TRIM(peliculas.clasificacion) <> '' "
    "ORDER BY peliculas.clasificacion"
)


def _valores_limpios(filas):
    valores = set()

    for fila in filas:
        valor = fila.get("valor")

        if type(valor) is str and valor.strip():
            valores.add(valor.strip())

    return sorted(valores, key=str.casefold)


def listar_generos():
    filas = consultar(SQL_GENEROS, (datetime.now(),))

    generos = set()

    for fila in filas:
        valor = fila.get("valor")

        if type(valor) is not str:
            continue

        for genero in valor.split(","):
            genero = genero.strip()

            if genero:
                generos.add(genero)

    return sorted(generos, key=str.casefold)


def listar_clasificaciones():
    filas = consultar(SQL_CLASIFICACIONES, (datetime.now(),))
    return _valores_limpios(filas)