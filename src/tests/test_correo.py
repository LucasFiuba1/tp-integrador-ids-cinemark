"""Pruebas del envío de emails de la factura con QR y del aviso de cancelación (SCRUM-67)."""
import os
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from src.backend.config import cargar_configuracion
from src.backend.services import correo
from src.backend.services.qr import generar_png
from src.backend.tokens import leer_cancelacion


def _compra_de_prueba(**cambios):
    compra = {
        "id": 88,
        "estado": "confirmada",
        "total": 23000.0,
        "funcion": {
            "id": 12,
            "fecha_hora": "2026-11-10T20:30:00",
            "pelicula_id": 3,
            "pelicula": "Volver al futuro",
            "poster_url": None,
            "sala": "Sala 1",
            "local": "Paradiso Centro",
        },
        "butacas": ["D5", "D6"],
        "servicios": [{"nombre": "Combo pochoclos grande", "cantidad": 2, "precio_unitario": 6500.0}],
        "cancelable": True,
        "cancelable_hasta": "2026-11-10T18:30:00",
    }
    compra.update(cambios)
    return compra


def _cliente_de_prueba():
    return {"nombre": "Ana Pérez", "email": "ana@email.com"}


@pytest.fixture
def app_con_smtp(app_backend):
    app_backend.config.update(
        SMTP_HOST="smtp.test.local",
        SMTP_PORT=587,
        SMTP_USER="cine@test.local",
        SMTP_PASSWORD="secreto-de-aplicacion",
        MAIL_FROM="entradas@cineparadiso.test",
        FRONTEND_URL="https://cine.test",
    )
    return app_backend


@pytest.fixture
def servidor_smtp():
    conexion = MagicMock()
    conexion.__enter__.return_value = conexion
    conexion.has_extn.return_value = True
    with patch("src.backend.services.correo.smtplib.SMTP", return_value=conexion) as constructor:
        yield SimpleNamespace(constructor=constructor, conexion=conexion)


from types import SimpleNamespace  # noqa: E402


def _partes_del_mensaje(mensaje):
    texto = mensaje.get_body(preferencelist=("plain",)).get_content()
    html = mensaje.get_body(preferencelist=("html",)).get_content()
    return texto, html


def test_enviar_factura_incluye_todos_los_datos_qr_embebido_adjunto_y_enlace_firmado(app_con_smtp, servidor_smtp):
    qr_png = b"\x89PNG\r\n\x1a\ndatos-qr"
    enviado = correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), qr_png)

    assert enviado is True
    servidor_smtp.constructor.assert_called_once_with("smtp.test.local", 587, timeout=correo.TIMEOUT_SEGUNDOS)
    servidor_smtp.conexion.starttls.assert_called_once()
    servidor_smtp.conexion.login.assert_called_once_with("cine@test.local", "secreto-de-aplicacion")

    [mensaje] = servidor_smtp.conexion.send_message.call_args.args
    assert mensaje["Subject"] == "Tu compra #88 en Cine Paradiso"
    assert mensaje["From"] == "entradas@cineparadiso.test"
    assert mensaje["To"] == "ana@email.com"

    texto, html = _partes_del_mensaje(mensaje)
    for fragmento in (
        "Ana Pérez", "Volver al futuro", "Paradiso Centro", "Sala 1",
        "10/11 · 20:30", "D5, D6", "Combo pochoclos grande × 2 ($6.500)", "$23.000", "#88",
    ):
        assert fragmento in texto
        assert fragmento in html

    enlace = correo.enlace_cancelacion(88)
    assert enlace.startswith("https://cine.test/cancelar/")
    assert enlace in texto and f'href="{enlace}"' in html
    token = enlace.rsplit("/", 1)[-1]
    assert leer_cancelacion(token) == 88

    adjuntos = list(mensaje.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "entrada-88.png"
    assert adjuntos[0].get_payload(decode=True) == qr_png

    [imagen_cid] = [parte for parte in mensaje.walk() if parte["Content-ID"]]
    assert imagen_cid.get_payload(decode=True) == qr_png
    cid_sin_angulos = imagen_cid["Content-ID"][1:-1]
    assert f'src="cid:{cid_sin_angulos}"' in html


def test_enviar_factura_sin_servicios_y_con_una_butaca_adapta_el_texto(app_con_smtp, servidor_smtp):
    compra = _compra_de_prueba(butacas=["A1"], servicios=[])
    assert correo.enviar_factura(compra, _cliente_de_prueba(), b"png") is True
    [mensaje] = servidor_smtp.conexion.send_message.call_args.args
    texto, html = _partes_del_mensaje(mensaje)
    assert "Butaca: A1" in texto and "<th>Butaca</th>" in html
    assert "Sin servicios" in texto and "Sin servicios" in html


def test_enviar_cancelacion_reutiliza_la_plantilla_sin_qr_ni_enlace(app_con_smtp, servidor_smtp):
    assert correo.enviar_cancelacion(_compra_de_prueba(estado="cancelada"), _cliente_de_prueba()) is True
    [mensaje] = servidor_smtp.conexion.send_message.call_args.args
    assert mensaje["Subject"] == "Cancelaste tu compra #88 en Cine Paradiso"
    texto, html = _partes_del_mensaje(mensaje)
    assert "Compra cancelada" in html and "Volver al futuro" in html and "$23.000" in html
    assert "Cancelar compra" not in html and "cid:" not in html
    assert list(mensaje.iter_attachments()) == []
    assert "cancelamos tu compra #88" in texto


def test_enviar_con_puerto_465_usa_smtp_ssl(app_con_smtp):
    app_con_smtp.config["SMTP_PORT"] = 465
    conexion = MagicMock()
    conexion.__enter__.return_value = conexion
    with patch("src.backend.services.correo.smtplib.SMTP_SSL", return_value=conexion) as smtp_ssl:
        assert correo.enviar_cancelacion(_compra_de_prueba(), _cliente_de_prueba()) is True
    smtp_ssl.assert_called_once()
    assert smtp_ssl.call_args.args == ("smtp.test.local", 465)


def test_enviar_sin_starttls_ni_usuario_no_inicia_tls_ni_hace_login(app_con_smtp, servidor_smtp):
    app_con_smtp.config["SMTP_USER"] = ""
    servidor_smtp.conexion.has_extn.return_value = False
    assert correo.enviar_cancelacion(_compra_de_prueba(), _cliente_de_prueba()) is True
    servidor_smtp.conexion.starttls.assert_not_called()
    servidor_smtp.conexion.login.assert_not_called()
    servidor_smtp.conexion.send_message.assert_called_once()


def test_enviar_sin_smtp_host_devuelve_false_y_no_conecta(app_con_smtp, servidor_smtp):
    app_con_smtp.config["SMTP_HOST"] = ""
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), b"png") is False
    servidor_smtp.constructor.assert_not_called()


@pytest.mark.parametrize(
    "excepcion",
    [
        smtplib.SMTPAuthenticationError(535, b"credenciales invalidas"),
        smtplib.SMTPConnectError(421, b"servicio no disponible"),
        smtplib.SMTPRecipientsRefused({"ana@email.com": (550, b"buzon inexistente")}),
        TimeoutError("tiempo agotado"),
        OSError("red inalcanzable"),
    ],
)
def test_enviar_captura_errores_smtp_y_de_red_devolviendo_false(app_con_smtp, servidor_smtp, excepcion):
    servidor_smtp.conexion.send_message.side_effect = excepcion
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), b"png") is False


def test_configuracion_toma_mail_from_de_smtp_user_y_quita_barra_final_de_frontend_url(monkeypatch):
    monkeypatch.setattr("src.backend.config.load_dotenv", lambda: None)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    monkeypatch.setenv("SMTP_USER", "cuenta@cine.com")
    monkeypatch.setenv("FRONTEND_URL", "https://cine.com/")
    config = cargar_configuracion()
    assert config["MAIL_FROM"] == "cuenta@cine.com"
    assert config["FRONTEND_URL"] == "https://cine.com"


@pytest.mark.skipif(
    not os.getenv("SMTP_PRUEBA_DESTINO"),
    reason="Definir SMTP_PRUEBA_DESTINO=casilla@real y las variables SMTP_* en .env para probar un envío real.",
)
def test_envio_real_a_casilla_configurada():
    from src.backend.app import create_app

    app = create_app()
    destino = os.environ["SMTP_PRUEBA_DESTINO"]
    with app.app_context():
        qr_png = generar_png("token-de-prueba-scrum-67")
        assert correo.enviar_factura(_compra_de_prueba(), {"nombre": "Equipo", "email": destino}, qr_png) is True
