"""Registro e inicio de sesión de usuarios (SCRUM-45)."""
import re

import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from src.backend.auth import generar_token
from src.backend.db import consultar_uno, ejecutar
from src.backend.errores import error_api

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAXIMO_NOMBRE = 100
MAXIMO_EMAIL = 150
MINIMO_PASSWORD = 8
MAXIMO_PASSWORD = 128


def _invalido(mensaje):
    error_api(400, "DATOS_INVALIDOS", mensaje)


def _email(valor):
    """Valida el email y lo devuelve sin espacios y en minúsculas, para que no se repita con otra capitalización."""
    if type(valor) is not str or len(valor.strip()) > MAXIMO_EMAIL or not PATRON_EMAIL.match(valor.strip()):
        _invalido("Ingresá un email válido, por ejemplo nombre@mail.com.")
    return valor.strip().lower()


def _password(valor):
    if type(valor) is not str or not MINIMO_PASSWORD <= len(valor) <= MAXIMO_PASSWORD:
        _invalido(f"La contraseña debe tener entre {MINIMO_PASSWORD} y {MAXIMO_PASSWORD} caracteres.")
    return valor


def registrar(datos):
    """Crea un usuario con rol cliente; los administradores solo se cargan desde seed.sql."""
    nombre = datos.get("nombre")
    if type(nombre) is not str or nombre.strip() == "" or len(nombre.strip()) > MAXIMO_NOMBRE:
        _invalido(f"El nombre es obligatorio y puede tener hasta {MAXIMO_NOMBRE} caracteres.")
    nombre = nombre.strip()
    email = _email(datos.get("email"))
    password_hash = generate_password_hash(_password(datos.get("password")), method="pbkdf2:sha256")
    try:
        nuevo_id = ejecutar(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, 'cliente')",
            (nombre, email, password_hash),
        )
    except pymysql.err.IntegrityError:
        # email es UNIQUE en la tabla usuarios
        error_api(409, "EMAIL_REGISTRADO", "Ya existe una cuenta con ese email.")
    return {"id": nuevo_id, "nombre": nombre, "email": email, "rol": "cliente"}


def iniciar_sesion(datos):
    """Devuelve el token si email y contraseña coinciden. El mensaje no dice cuál de los dos falló."""
    email, password = datos.get("email"), datos.get("password")
    if type(email) is not str or type(password) is not str or email.strip() == "" or password == "":
        _invalido("Ingresá tu email y tu contraseña.")
    usuario = consultar_uno(
        "SELECT id, nombre, password_hash, rol FROM usuarios WHERE email = %s", (email.strip().lower(),)
    )
    if usuario is None or not check_password_hash(usuario["password_hash"], password):
        error_api(401, "CREDENCIALES_INVALIDAS", "El email o la contraseña son incorrectos.")
    return {"token": generar_token(usuario["id"]), "rol": usuario["rol"], "nombre": usuario["nombre"]}
