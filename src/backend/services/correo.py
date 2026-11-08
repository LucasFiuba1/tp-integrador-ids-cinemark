"""Emails de la compra: factura con el QR y el enlace de cancelación, y aviso de cancelación (SCRUM-67).

SMTP con la librería estándar (smtplib + email.message); servidor y credenciales salen de .env (SMTP_*, MAIL_FROM).
Las funciones públicas nunca cortan el request: devuelven True si el servidor aceptó el mensaje y False si no,
y dejan el motivo en el log. Así una falla del correo no deshace una compra ya confirmada.
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from flask import current_app, render_template

from src.backend.tokens import firmar_cancelacion

TIMEOUT_SEGUNDOS = 10
PUERTO_SSL = 465


def enlace_cancelacion(compra_id):
    """URL de la página de cancelación del frontend, con el token firmado que identifica la compra."""
    return f"{current_app.config['FRONTEND_URL']}/cancelar/{firmar_cancelacion(compra_id)}"


def enviar_factura(compra, cliente, qr_png):
    """Envía la factura de una compra confirmada.

    compra: dict de perfil.obtener_compra · cliente: {"nombre", "email"} · qr_png: bytes del PNG del QR.
    El QR va embebido en el cuerpo (cid) y también adjunto, por si el cliente de correo bloquea las imágenes.
    """
    cid = make_msgid(domain="cine-paradiso")
    contexto = {
        "compra": compra, "cliente": cliente, "qr_cid": cid[1:-1],
        "enlace_cancelacion": enlace_cancelacion(compra["id"]),
    }

    def agregar_qr(mensaje):
        cuerpo_html = mensaje.get_body(preferencelist=("html",))
        cuerpo_html.add_related(qr_png, maintype="image", subtype="png", cid=cid)
        mensaje.add_attachment(qr_png, maintype="image", subtype="png", filename=f"entrada-{compra['id']}.png")

    asunto = f"Tu compra #{compra['id']} en Cine Paradiso"
    return _enviar(asunto, cliente["email"], "factura", contexto, compra["id"], agregar_qr)


def enviar_cancelacion(compra, cliente):
    """Avisa que la compra se canceló (lo usa la cancelación, SCRUM-69/70). Mismo detalle que la factura, sin QR."""
    asunto = f"Cancelaste tu compra #{compra['id']} en Cine Paradiso"
    return _enviar(asunto, cliente["email"], "cancelacion", {"compra": compra, "cliente": cliente}, compra["id"])


def _armar(asunto, destinatario, plantilla, contexto):
    """Mensaje con versión en texto y en HTML, renderizadas desde templates/email/<plantilla>.txt|.html."""
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = current_app.config["MAIL_FROM"]
    mensaje["To"] = destinatario
    mensaje.set_content(render_template(f"email/{plantilla}.txt", **contexto))
    mensaje.add_alternative(render_template(f"email/{plantilla}.html", **contexto), subtype="html")
    return mensaje


def _conectar(config):
    if config["SMTP_PORT"] == PUERTO_SSL:
        return smtplib.SMTP_SSL(
            config["SMTP_HOST"], config["SMTP_PORT"], timeout=TIMEOUT_SEGUNDOS, context=ssl.create_default_context()
        )
    conexion = smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=TIMEOUT_SEGUNDOS)
    conexion.ehlo()
    if conexion.has_extn("starttls"):
        conexion.starttls(context=ssl.create_default_context())
        conexion.ehlo()
    return conexion


def _enviar(asunto, destinatario, plantilla, contexto, compra_id, completar=None):
    config = current_app.config
    if not config["SMTP_HOST"]:
        current_app.logger.warning("No se envió el email de la compra %s: falta configurar SMTP_HOST.", compra_id)
        return False
    try:
        mensaje = _armar(asunto, destinatario, plantilla, contexto)
        if completar is not None:
            completar(mensaje)
        with _conectar(config) as conexion:
            if config["SMTP_USER"]:
                conexion.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            conexion.send_message(mensaje)
    except (smtplib.SMTPException, OSError, ValueError) as error:
        current_app.logger.error("No se pudo enviar el email de la compra %s: %s", compra_id, error)
        return False
    return True

