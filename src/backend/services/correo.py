"""Emails de la compra (factura con el QR y el enlace de cancelación, aviso de cancelación; SCRUM-67) y de
recuperación de contraseña.

Se envían por HTTPS con Mailjet Send API v3.1, sin SMTP: los hostings gratuitos suelen bloquear los puertos SMTP
salientes. Las claves (MAILJET_API_KEY, MAILJET_SECRET_KEY) y el remitente verificado (MAIL_FROM) salen de .env.
Las funciones públicas devuelven True si Mailjet aceptó el mensaje (200, Status success y MessageID) y False si no
(configuración faltante, error de red o de requests, respuesta inválida o falla controlada del template), y dejan el
motivo en el log. Así una falla del correo no deshace una compra ya confirmada. Los errores de programación
(TypeError, KeyError, RuntimeError...) no se capturan: se propagan para no ocultarlos.

El log nunca incluye la clave, el destinatario, el token ni el QR, ni el texto de las excepciones de requests
(puede traer la URL o cabeceras): solo el id de la compra (o del usuario), el status HTTP y el tipo de la excepción.
"""
import base64

import requests
from flask import current_app, render_template
from jinja2 import TemplateError

from src.backend.tokens import VIGENCIA_RECUPERACION_SEGUNDOS, firmar_cancelacion

URL_MAILJET = "https://api.mailjet.com/v3.1/send"
TIMEOUT_SEGUNDOS = 10
NOMBRE_REMITENTE = "Cine Paradiso"


def enlace_cancelacion(compra_id):
    """URL de la página de cancelación del frontend, con el token firmado que identifica la compra."""
    return f"{current_app.config['FRONTEND_URL']}/cancelar/{firmar_cancelacion(compra_id)}"


def enviar_factura(compra, cliente, qr_png):
    """Envía la factura de una compra confirmada.

    compra: dict de perfil.obtener_compra · cliente: {"nombre", "email"} · qr_png: bytes del PNG del QR.
    El QR se incrusta solo en el HTML, por Content-ID (InlinedAttachments); no se adjunta como archivo aparte.
    """
    cid = f"qr-compra-{compra['id']}"
    contexto = {
        "compra": compra, "cliente": cliente, "enlace_cancelacion": enlace_cancelacion(compra["id"]), "qr_cid": cid,
    }
    imagen = {
        "ContentType": "image/png", "Filename": f"qr-{compra['id']}.png",
        "Base64Content": base64.b64encode(qr_png).decode("ascii"), "ContentID": cid,
    }
    asunto = f"Tu compra #{compra['id']} en Cine Paradiso"
    return _enviar(asunto, cliente, "factura", contexto, _de_compra(compra), [imagen])


def enviar_cancelacion(compra, cliente):
    """Avisa que la compra se canceló (lo usa la cancelación, SCRUM-69/70). Mismo detalle que la factura, sin QR."""
    asunto = f"Cancelaste tu compra #{compra['id']} en Cine Paradiso"
    return _enviar(asunto, cliente, "cancelacion", {"compra": compra, "cliente": cliente}, _de_compra(compra))


def enviar_recuperacion(usuario, token):
    """Manda el enlace para restablecer la contraseña. usuario: {"id", "nombre", "email"} · token: firmar_recuperacion."""
    contexto = {
        "cliente": usuario,
        "enlace": f"{current_app.config['FRONTEND_URL']}/restablecer/{token}",
        "minutos_vigencia": VIGENCIA_RECUPERACION_SEGUNDOS // 60,
    }
    asunto = "Restablecé tu contraseña de Cine Paradiso"
    return _enviar(asunto, usuario, "recuperar_password", contexto, f"de recuperación del usuario {usuario['id']}")


def _de_compra(compra):
    return f"de la compra {compra['id']}"


def _armar(asunto, remitente, cliente, plantilla, contexto, imagenes):
    """Cuerpo JSON de Mailjet con las versiones HTML y texto renderizadas desde templates/email/<plantilla>.*"""
    destinatario = {"Email": cliente["email"]}
    if cliente.get("nombre"):
        destinatario["Name"] = cliente["nombre"]
    mensaje = {
        "From": {"Name": NOMBRE_REMITENTE, "Email": remitente},
        "To": [destinatario],
        "Subject": asunto,
        "HTMLPart": render_template(f"email/{plantilla}.html", **contexto),
        "TextPart": render_template(f"email/{plantilla}.txt", **contexto),
    }
    if imagenes:
        mensaje["InlinedAttachments"] = imagenes
    return {"Messages": [mensaje]}


def _mensaje_aceptado(respuesta):
    try:
        datos = respuesta.json()
    except ValueError:
        return False
    mensajes = datos.get("Messages") if isinstance(datos, dict) else None
    if not isinstance(mensajes, list) or len(mensajes) != 1:
        return False
    mensaje = mensajes[0]
    if not isinstance(mensaje, dict) or mensaje.get("Status") != "success":
        return False
    destinatarios = mensaje.get("To")
    if not isinstance(destinatarios, list) or len(destinatarios) != 1 or not isinstance(destinatarios[0], dict):
        return False
    message_id = destinatarios[0].get("MessageID")
    return (type(message_id) is int and message_id > 0) or (
        isinstance(message_id, str) and message_id.isascii() and message_id.isdecimal() and bool(message_id.strip("0"))
    )


def _enviar(asunto, cliente, plantilla, contexto, referencia, imagenes=None):
    """referencia identifica el email en el log sin datos personales, por ejemplo "de la compra 88"."""
    config = current_app.config
    clave = (config.get("MAILJET_API_KEY") or "").strip()
    secreto = (config.get("MAILJET_SECRET_KEY") or "").strip()
    remitente = (config.get("MAIL_FROM") or "").strip()
    if not clave or not secreto or not remitente:
        current_app.logger.warning(
            "No se envió el email %s: falta configurar MAILJET_API_KEY, MAILJET_SECRET_KEY o MAIL_FROM.",
            referencia,
        )
        return False
    try:
        cuerpo = _armar(asunto, remitente, cliente, plantilla, contexto, imagenes)
        respuesta = requests.post(
            URL_MAILJET,
            json=cuerpo,
            auth=(clave, secreto),
            headers={"accept": "application/json"},
            timeout=TIMEOUT_SEGUNDOS,
            allow_redirects=False,
        )
    except (requests.RequestException, TemplateError) as error:  # el texto puede traer datos sensibles: no se loguea
        current_app.logger.error(
            "No se pudo enviar el email %s: %s.", referencia, type(error).__name__
        )
        return False
    if respuesta.status_code != 200:
        current_app.logger.error(
            "Mailjet rechazó el email %s: HTTP %s.", referencia, respuesta.status_code
        )
        return False
    if not _mensaje_aceptado(respuesta):
        current_app.logger.error("Mailjet no confirmó la aceptación del email %s.", referencia)
        return False
    return True
