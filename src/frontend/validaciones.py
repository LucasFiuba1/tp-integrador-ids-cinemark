"""Validaciones de los formularios del frontend.

Cada función recibe el formulario ya leído (dict de strings) y devuelve un dict campo -> mensaje de error.
Si el dict está vacío, el formulario es válido. Los límites siguen a docs/base_de_datos.md (VARCHAR del schema).
"""
import re
from datetime import date
from urllib.parse import parse_qs, urlsplit

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_VENCIMIENTO = re.compile(r"^(0[1-9]|1[0-2])/(\d{2})$")
PATRON_CODIGO_SEGURIDAD = re.compile(r"^\d{3,4}$")
DIGITOS_TARJETA = (13, 19)

MAXIMO_EMAIL = 150
MAXIMO_NOMBRE = 100
MINIMO_PASSWORD = 8
MAXIMO_CODIGO_QR = 500
MAXIMO_DESCRIPCION = 255
MAXIMO_PRECIO = 99_999_999.99  # DECIMAL(10, 2)
MAXIMO_DIRECCION = 200
MAXIMO_NOMBRE_SALA = 50
MAXIMO_FILAS = 26  # una letra por fila (A a Z)
MAXIMO_COLUMNAS = 30
MAXIMO_CANTIDAD_SERVICIO = 20  # el mismo tope que valida el backend en PUT /api/compras/<id>/servicios


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


def _error_texto(valor, mensaje_vacio, maximo=MAXIMO_NOMBRE, que="El nombre"):
    if not valor:
        return mensaje_vacio
    if len(valor) > maximo:
        return f"{que} puede tener hasta {maximo} caracteres."
    return None


def _sin_vacios(errores):
    return {campo: mensaje for campo, mensaje in errores.items() if mensaje}


def validar_login(datos):
    return _sin_vacios({
        "email": _error_email(datos["email"]),
        "password": None if datos["password"] else "Ingresá tu contraseña.",
    })


def validar_registro(datos):
    password = datos["password"]
    return _sin_vacios({
        "nombre": _error_texto(datos["nombre"], "Ingresá tu nombre."),
        "email": _error_email(datos["email"]),
        "password": None if len(password) >= MINIMO_PASSWORD
        else f"La contraseña debe tener al menos {MINIMO_PASSWORD} caracteres.",
        "repetir_password": None if datos["repetir_password"] == password else "Las contraseñas no coinciden.",
    })


def _error_numero_tarjeta(numero):
    digitos = numero.replace(" ", "").replace("-", "")
    if not digitos:
        return "Ingresá el número de la tarjeta."
    if not digitos.isdecimal() or not DIGITOS_TARJETA[0] <= len(digitos) <= DIGITOS_TARJETA[1]:
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
    return _sin_vacios({
        "titular": _error_texto(datos["titular"], "Ingresá el nombre del titular como figura en la tarjeta."),
        "numero": _error_numero_tarjeta(datos["numero"]),
        "vencimiento": _error_vencimiento(datos["vencimiento"], hoy or date.today()),
        "codigo_seguridad": None if PATRON_CODIGO_SEGURIDAD.match(datos["codigo_seguridad"])
        else "El código de seguridad tiene 3 o 4 dígitos.",
        "acepto": None if datos["acepto"] else "Tenés que aceptar los términos y la política de cancelación.",
    })


def _error_token_qr(token):
    if not token:
        return "Escaneá el QR con la cámara o pegá el código de la entrada."
    if len(token) > MAXIMO_CODIGO_QR:
        return "El código es demasiado largo; revisá que sea el de la entrada."
    return None


def token_del_qr(texto):
    """El QR de la entrada es la URL /admin/ingreso?token=... Si el lector (o el admin) pega la URL entera, se usa
    solo el token; cualquier otro texto se devuelve tal cual para que lo valide el backend (SCRUM-81)."""
    partes = urlsplit(texto)
    if partes.scheme in ("http", "https"):
        return parse_qs(partes.query).get("token", [texto])[0].strip()
    return texto


def validar_ingreso(datos):
    """Formulario de validar ingreso: {"funcion_id", "token"} -> errores por campo (vacío si está bien)."""
    funcion_id = datos["funcion_id"]
    return _sin_vacios({
        "funcion_id": None if funcion_id.isdecimal() and int(funcion_id) > 0
        else "Elegí la función que estás controlando.",
        "token": _error_token_qr(datos["token"]),
    })


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
    return _sin_vacios({
        "nombre": _error_texto(datos["nombre"], "Ingresá el nombre del servicio."),
        "descripcion": None if len(datos["descripcion"]) <= MAXIMO_DESCRIPCION
        else f"La descripción puede tener hasta {MAXIMO_DESCRIPCION} caracteres.",
        "precio": _error_precio(datos["precio"]),
    })


def _fecha_o_none(texto):
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _error_hasta(desde, hasta):
    if not hasta:
        return "Ingresá una fecha válida."
    if desde and hasta < desde:
        return "Tiene que ser igual o posterior a la fecha desde."
    return None


def validar_filtros_dashboards(datos):
    """Fechas desde y hasta de los filtros GET de los dashboards, en YYYY-MM-DD (input date)."""
    desde, hasta = _fecha_o_none(datos["desde"]), _fecha_o_none(datos["hasta"])
    return _sin_vacios({
        "desde": None if desde else "Ingresá una fecha válida.",
        "hasta": _error_hasta(desde, hasta),
    })


def _error_entero(texto, que, maximo, minimo=1):
    # El largo se mira antes de int(): con miles de dígitos, int() corta con ValueError y la página daría error 500.
    if not texto.isdecimal() or len(texto) > len(str(maximo)) or not minimo <= int(texto) <= maximo:
        return f"{que} tiene que ser un número entero entre {minimo} y {maximo}."
    return None


def validar_local(datos):
    return _sin_vacios({
        "nombre": _error_texto(datos["nombre"], "Ingresá el nombre del local."),
        "direccion": _error_texto(datos["direccion"], "Ingresá la dirección del local.", MAXIMO_DIRECCION,
                                  "La dirección"),
    })


def validar_sala(datos):
    return _sin_vacios({
        "nombre": _error_texto(datos["nombre"], "Ingresá el nombre de la sala.", MAXIMO_NOMBRE_SALA),
        "filas": _error_entero(datos["filas"], "La cantidad de filas", MAXIMO_FILAS),
        "columnas": _error_entero(datos["columnas"], "La cantidad de butacas por fila", MAXIMO_COLUMNAS),
    })


def validar_cantidades_servicios(cantidades):
    """cantidades: {servicio_id: texto del campo}. Un campo vacío ya llega como "0" (no agrega ese servicio)."""
    return _sin_vacios({
        servicio_id: _error_entero(texto, "La cantidad", MAXIMO_CANTIDAD_SERVICIO, minimo=0)
        for servicio_id, texto in cantidades.items()
    })
