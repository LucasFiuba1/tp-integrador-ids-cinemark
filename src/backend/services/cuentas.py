"""Registro e inicio de sesión de usuarios (SCRUM-45)."""
import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from src.backend.auth import generar_token
from src.backend.db import consultar_uno, ejecutar
from src.backend.errores import error_api
from src.backend.services.validaciones import datos_invalidos, email_valido, texto_no_vacio

MAXIMO_NOMBRE = 100
MINIMO_PASSWORD = 8
MAXIMO_PASSWORD = 128


def _password(valor):
    if type(valor) is not str or not MINIMO_PASSWORD <= len(valor) <= MAXIMO_PASSWORD:
        datos_invalidos(f"La contraseña debe tener entre {MINIMO_PASSWORD} y {MAXIMO_PASSWORD} caracteres.")
    return valor


def registrar(datos):
    """Crea un usuario con rol cliente; los administradores solo se cargan desde seed.sql."""
    nombre = texto_no_vacio(datos.get("nombre"), "nombre", MAXIMO_NOMBRE)
    email = email_valido(datos.get("email"))
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
        datos_invalidos("Ingresá tu email y tu contraseña.")
    usuario = consultar_uno(
        "SELECT id, nombre, password_hash, rol FROM usuarios WHERE email = %s", (email.strip().lower(),)
    )
    if usuario is None or not check_password_hash(usuario["password_hash"], password):
        error_api(401, "CREDENCIALES_INVALIDAS", "El email o la contraseña son incorrectos.")
    return {"token": generar_token(usuario["id"]), "rol": usuario["rol"], "nombre": usuario["nombre"]}
