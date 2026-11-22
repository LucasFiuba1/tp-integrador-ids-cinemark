"""Registro, inicio de sesión y recuperación de contraseña de usuarios (SCRUM-45)."""
from werkzeug.security import check_password_hash, generate_password_hash

from src.backend.abm import traducir_duplicado
from src.backend.auth import generar_token
from src.backend.db import consultar_uno, ejecutar
from src.backend.errores import error_api
from src.backend.services import correo
from src.backend.services.validaciones import datos_invalidos, email_valido, texto_no_vacio
from src.backend.tokens import firmar_recuperacion, huella_password, leer_recuperacion

MAXIMO_NOMBRE = 100
MINIMO_PASSWORD = 8
MAXIMO_PASSWORD = 128


def _password(valor):
    if type(valor) is not str or not MINIMO_PASSWORD <= len(valor) <= MAXIMO_PASSWORD:
        datos_invalidos(f"La contraseña debe tener entre {MINIMO_PASSWORD} y {MAXIMO_PASSWORD} caracteres.")
    return valor


def _hashear(password):
    return generate_password_hash(_password(password), method="pbkdf2:sha256")


def registrar(datos):
    """Crea un usuario con rol cliente; los administradores solo se cargan desde seed.sql."""
    nombre = texto_no_vacio(datos.get("nombre"), "nombre", MAXIMO_NOMBRE)
    email = email_valido(datos.get("email"))
    password_hash = _hashear(datos.get("password"))
    # email es UNIQUE en la tabla usuarios
    with traducir_duplicado("Ya existe una cuenta con ese email.", "EMAIL_REGISTRADO"):
        nuevo_id = ejecutar(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, 'cliente')",
            (nombre, email, password_hash),
        )
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


MENSAJE_RECUPERACION = "Si el email corresponde a una cuenta, te enviamos un enlace para restablecer la contraseña."


def solicitar_recuperacion(datos):
    """Envía el enlace de recuperación si el email es de una cuenta. La respuesta es la misma exista o no la cuenta
    (y aunque el email no salga), para no revelar qué emails están registrados."""
    email = email_valido(datos.get("email"))
    usuario = consultar_uno("SELECT id, nombre, email, password_hash FROM usuarios WHERE email = %s", (email,))
    if usuario is not None:
        correo.enviar_recuperacion(usuario, firmar_recuperacion(usuario["id"], usuario["password_hash"]))
    return {"mensaje": MENSAJE_RECUPERACION}


def _usuario_del_token(token):
    """Usuario {"id", "password_hash"} dueño de un token de recuperación vigente; corta con 400 si no sirve."""
    leido = leer_recuperacion(token)
    usuario = None
    if leido is not None:
        usuario = consultar_uno("SELECT id, password_hash FROM usuarios WHERE id = %s", (leido[0],))
    # La huella cambia con la contraseña: un enlace ya usado (o anterior a otro cambio) deja de servir.
    if usuario is None or huella_password(usuario["password_hash"]) != leido[1]:
        error_api(400, "TOKEN_INVALIDO", "El enlace para restablecer la contraseña no es válido o venció. Pedí uno nuevo.")
    return usuario


def validar_recuperacion(token):
    """Para que el frontend avise antes de mostrar el formulario si el enlace ya no sirve."""
    _usuario_del_token(token)
    return {"valido": True}


def restablecer_password(datos):
    usuario = _usuario_del_token(datos.get("token"))
    password_hash = _hashear(datos.get("password"))
    ejecutar("UPDATE usuarios SET password_hash = %s WHERE id = %s", (password_hash, usuario["id"]))
    return {"mensaje": "Listo, ya podés ingresar con tu nueva contraseña."}
