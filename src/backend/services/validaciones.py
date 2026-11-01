"""Validaciones compartidas para los datos recibidos por la API."""
import re
from datetime import datetime

from src.backend.errores import error_api

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FORMATO_FECHA_HORA = "%Y-%m-%dT%H:%M:%S"


def _invalido(mensaje):
    error_api(400, "DATOS_INVALIDOS", mensaje)


def requerir_campos(datos, campos):
    if not isinstance(datos, dict):
        _invalido("El cuerpo debe ser un objeto JSON.")
    faltantes = [campo for campo in campos if campo not in datos]
    if faltantes:
        _invalido("Faltan campos obligatorios: " + ", ".join(faltantes) + ".")


def entero_positivo(valor, campo):
    if type(valor) is not int or valor <= 0:
        _invalido(f"{campo} debe ser un entero positivo.")
    return valor


def texto_no_vacio(valor, campo, maximo=None):
    if type(valor) is not str or not valor.strip():
        _invalido(f"{campo} debe ser un texto no vacío.")
    texto = valor.strip()
    if maximo is not None and len(texto) > maximo:
        _invalido(f"{campo} no puede superar los {maximo} caracteres.")
    return texto


def email_valido(valor):
    email = texto_no_vacio(valor, "email", 150)
    if not PATRON_EMAIL.fullmatch(email):
        _invalido("email debe tener un formato válido.")
    return email.lower()


def fecha_hora_iso(valor, campo):
    if type(valor) is not str:
        _invalido(f"{campo} debe tener formato YYYY-MM-DDTHH:MM:SS.")
    try:
        fecha = datetime.strptime(valor, FORMATO_FECHA_HORA)
    except ValueError as error:
        _invalido(f"{campo} debe tener formato YYYY-MM-DDTHH:MM:SS.")
    if fecha.strftime(FORMATO_FECHA_HORA) != valor:
        _invalido(f"{campo} debe tener formato YYYY-MM-DDTHH:MM:SS.")
    return fecha
