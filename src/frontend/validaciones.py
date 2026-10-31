"""Validaciones de los formularios del frontend.

Cada función recibe el formulario ya leído (dict de strings) y devuelve un dict campo -> mensaje de error.
Si el dict está vacío, el formulario es válido. Los límites siguen a docs/base_de_datos.md (VARCHAR del schema).
"""
import re

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAXIMO_EMAIL = 150
MAXIMO_NOMBRE = 100
MINIMO_PASSWORD = 8
MAXIMO_CODIGO_QR = 500
MAXIMO_DESCRIPCION = 255
MAXIMO_PRECIO = 99_999_999.99  # DECIMAL(10, 2)


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


def validar_codigo_qr(datos):
    codigo = datos["codigo"]
    if not codigo:
        return {"codigo": "Ingresá o escaneá el código de la entrada."}
    if len(codigo) > MAXIMO_CODIGO_QR:
        return {"codigo": "El código es demasiado largo; revisá que sea el de la entrada."}
    return {}


def _error_precio(texto):
    if not texto:
        return "Ingresá el precio."
    try:
        precio = float(texto.replace(",", "."))
    except ValueError:
        return "El precio tiene que ser un número, por ejemplo 2500."
    if not 0 < precio <= MAXIMO_PRECIO:
        return "El precio tiene que ser mayor a $0 y menor a $100.000.000."
    return None


def validar_servicio(datos):
    nombre = datos["nombre"]
    if not nombre:
        error_nombre = "Ingresá el nombre del servicio."
    elif len(nombre) > MAXIMO_NOMBRE:
        error_nombre = f"El nombre puede tener hasta {MAXIMO_NOMBRE} caracteres."
    else:
        error_nombre = None

    return _sin_vacios({
        "nombre": error_nombre,
        "descripcion": None if len(datos["descripcion"]) <= MAXIMO_DESCRIPCION
        else f"La descripción puede tener hasta {MAXIMO_DESCRIPCION} caracteres.",
        "precio": _error_precio(datos["precio"]),
    })
