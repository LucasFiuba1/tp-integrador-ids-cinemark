"""Registro y autenticación de usuarios."""
import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from src.backend.auth import generar_token
from src.backend.db import consultar_uno, ejecutar
from src.backend.errores import error_api
from src.backend.services.validaciones import email_valido, requerir_campos, texto_no_vacio

MINIMO_PASSWORD = 8
MAXIMO_PASSWORD = 128


def registrar(datos):
    requerir_campos(datos, ("nombre", "email", "password"))
    nombre = texto_no_vacio(datos["nombre"], "nombre", 100)
    email = email_valido(datos["email"])
    password = datos["password"]
    if type(password) is not str or not MINIMO_PASSWORD <= len(password) <= MAXIMO_PASSWORD:
        error_api(
            400, "DATOS_INVALIDOS",
            f"password debe tener entre {MINIMO_PASSWORD} y {MAXIMO_PASSWORD} caracteres.",
        )
    if consultar_uno("SELECT id FROM usuarios WHERE email = %s", (email,)) is not None:
        error_api(409, "EMAIL_DUPLICADO", "Ya existe una cuenta con ese email.")
    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    try:
        usuario_id = ejecutar(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
            (nombre, email, password_hash, "cliente"),
        )
    except pymysql.err.IntegrityError:
        error_api(409, "EMAIL_DUPLICADO", "Ya existe una cuenta con ese email.")
    return {"id": usuario_id, "nombre": nombre, "email": email, "rol": "cliente"}


def iniciar_sesion(datos):
    requerir_campos(datos, ("email", "password"))
    email = email_valido(datos["email"])
    password = datos["password"]
    if type(password) is not str or not password or len(password) > MAXIMO_PASSWORD:
        error_api(401, "CREDENCIALES_INVALIDAS", "El email o la contraseña son incorrectos.")
    usuario = consultar_uno(
        "SELECT id, nombre, email, rol, password_hash FROM usuarios WHERE email = %s", (email,)
    )
    if usuario is None or not check_password_hash(usuario["password_hash"], password):
        error_api(401, "CREDENCIALES_INVALIDAS", "El email o la contraseña son incorrectos.")
    return {"token": generar_token(usuario["id"]), "rol": usuario["rol"], "nombre": usuario["nombre"]}


def obtener_actual(usuario):
    return {"id": usuario["id"], "nombre": usuario["nombre"], "rol": usuario["rol"]}
