"""Validaciones de los formularios del frontend.

Cada función recibe el formulario ya leído (dict de strings) y devuelve un dict campo -> mensaje de error.
Si el dict está vacío, el formulario es válido. Los límites siguen a docs/base_de_datos.md (VARCHAR del schema).
"""
import re
from datetime import date

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_VENCIMIENTO = re.compile(r"^(0[1-9]|1[0-2])/(\d{2})$")
PATRON_CODIGO_SEGURIDAD = re.compile(r"^\d{3,4}$")
DIGITOS_TARJETA = (13, 19)

MAXIMO_EMAIL = 150
MAXIMO_NOMBRE = 100
MINIMO_PASSWORD = 8
MAXIMO_CODIGO_QR = 500


def leer_formulario(formulario, *campos):
    """Toma los campos pedidos de request.form sin espacios en los extremos (salvo contraseñas, que van tal cual)."""
    return {
        campo: formulario.get(campo, "") if "password" in campo else formulario.get(campo, "").strip()
        for campo in campos
    }


def _error_email(email):
    if not email:
        return "Ingresá tu email."
    if len(email) > MAXIMO_EMAIL or not PATRON_EMAIL.match(email):
        return "Ingresá un email válido, por ejemplo nombre@mail.com."
    return None


def _sin_vacios(errores):
    return {campo: mensaje for campo, mensaje in errores.items() if mensaje}


def validar_login(datos):
    return _sin_vacios({
        "email": _error_email(datos["email"]),
        "password": None if datos["password"] else "Ingresá tu contraseña.",
    })


def validar_registro(datos):
    nombre, password = datos["nombre"], datos["password"]
    if not nombre:
        error_nombre = "Ingresá tu nombre."
    elif len(nombre) > MAXIMO_NOMBRE:
        error_nombre = f"El nombre puede tener hasta {MAXIMO_NOMBRE} caracteres."
    else:
        error_nombre = None

    if len(password) < MINIMO_PASSWORD:
        error_password = f"La contraseña debe tener al menos {MINIMO_PASSWORD} caracteres."
    else:
        error_password = None

    return _sin_vacios({
        "nombre": error_nombre,
        "email": _error_email(datos["email"]),
        "password": error_password,
        "repetir_password": None if datos["repetir_password"] == password else "Las contraseñas no coinciden.",
    })


def _error_numero_tarjeta(numero):
    digitos = numero.replace(" ", "").replace("-", "")
    if not digitos:
        return "Ingresá el número de la tarjeta."
    if not digitos.isdigit() or not DIGITOS_TARJETA[0] <= len(digitos) <= DIGITOS_TARJETA[1]:
        return f"El número tiene que tener entre {DIGITOS_TARJETA[0]} y {DIGITOS_TARJETA[1]} dígitos."
    return None


def _error_vencimiento(vencimiento, hoy):
    coincidencia = PATRON_VENCIMIENTO.match(vencimiento)
    if not coincidencia:
        return "Ingresá el vencimiento como MM/AA, por ejemplo 12/28."
    mes, anio = int(coincidencia.group(1)), 2000 + int(coincidencia.group(2))
    if (anio, mes) < (hoy.year, hoy.month):
        return "La tarjeta está vencida."
    return None


def validar_pago(datos, hoy=None):
    """Datos de la tarjeta del pago simulado. hoy se recibe para poder probar el vencimiento con una fecha fija."""
    titular = datos["titular"]
    if not titular:
        error_titular = "Ingresá el nombre del titular como figura en la tarjeta."
    elif len(titular) > MAXIMO_NOMBRE:
        error_titular = f"El nombre puede tener hasta {MAXIMO_NOMBRE} caracteres."
    else:
        error_titular = None

    return _sin_vacios({
        "titular": error_titular,
        "numero": _error_numero_tarjeta(datos["numero"]),
        "vencimiento": _error_vencimiento(datos["vencimiento"], hoy or date.today()),
        "codigo_seguridad": None if PATRON_CODIGO_SEGURIDAD.match(datos["codigo_seguridad"])
        else "El código de seguridad tiene 3 o 4 dígitos.",
        "acepto": None if datos["acepto"] else "Tenés que aceptar los términos y la política de cancelación.",
    })


def validar_codigo_qr(datos):
    codigo = datos["codigo"]
    if not codigo:
        return {"codigo": "Ingresá o escaneá el código de la entrada."}
    if len(codigo) > MAXIMO_CODIGO_QR:
        return {"codigo": "El código es demasiado largo; revisá que sea el de la entrada."}
    return {}
