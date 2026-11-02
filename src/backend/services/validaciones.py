"""Validaciones compartidas para los datos recibidos por la API.

Cada función devuelve el valor ya limpio o corta el request con 400 DATOS_INVALIDOS. Los services las usan en vez
de repetir sus propios chequeos.
"""
import re
from datetime import datetime

from src.backend.errores import error_api

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FORMATO_FECHA_HORA = "%Y-%m-%dT%H:%M:%S"
MAXIMO_EMAIL = 150


def datos_invalidos(mensaje):
    error_api(400, "DATOS_INVALIDOS", mensaje)


def requerir_campos(datos, campos):
    if not isinstance(datos, dict):
        datos_invalidos("El cuerpo debe ser un objeto JSON.")
    faltantes = [campo for campo in campos if campo not in datos]
    if faltantes:
        datos_invalidos("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")


def entero_en_rango(valor, campo, minimo, maximo):
    """type() y no isinstance(): True y False son int en Python y no deben pasar como números."""
    if type(valor) is not int or not minimo <= valor <= maximo:
        datos_invalidos(f"{campo} debe ser un número entero entre {minimo} y {maximo}.")
    return valor


def entero_positivo(valor, campo):
    if type(valor) is not int or valor <= 0:
        datos_invalidos(f"{campo} debe ser un entero positivo.")
    return valor


def entero_positivo_texto(texto, campo):
    """Para parámetros de la URL (?local_id=3). isdecimal() y no isdigit(): "²" es dígito pero int("²") falla."""
    if not texto.isdecimal() or int(texto) == 0:
        datos_invalidos(f"{campo} debe ser un entero positivo.")
    return int(texto)


def texto_no_vacio(valor, campo, maximo=None):
    if type(valor) is not str or not valor.strip():
        datos_invalidos(f"{campo} debe ser un texto no vacío.")
    texto = valor.strip()
    if maximo is not None and len(texto) > maximo:
        datos_invalidos(f"{campo} no puede superar los {maximo} caracteres.")
    return texto


def email_valido(valor):
    """Devuelve el email sin espacios y en minúsculas, para que no se repita con otra capitalización."""
    if type(valor) is not str or len(valor.strip()) > MAXIMO_EMAIL or not PATRON_EMAIL.fullmatch(valor.strip()):
        datos_invalidos("Ingresá un email válido, por ejemplo nombre@mail.com.")
    return valor.strip().lower()


def fecha_hora_iso(valor, campo):
    mensaje = f"{campo} debe tener formato YYYY-MM-DDTHH:MM:SS."
    if type(valor) is not str:
        datos_invalidos(mensaje)
    try:
        fecha = datetime.strptime(valor, FORMATO_FECHA_HORA)
    except ValueError:
        datos_invalidos(mensaje)
    if fecha.strftime(FORMATO_FECHA_HORA) != valor:
        datos_invalidos(mensaje)
    return fecha
