"""Pruebas del envío por Mailjet HTTPS: factura con QR embebido (sin adjuntos), y aviso de cancelación (SCRUM-67).

Ninguna prueba sale a la red, salvo el envío real optativo: la app de prueba parte sin credenciales de Mailjet.
"""
import base64
import logging
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests
from jinja2 import TemplateNotFound

from src.backend.config import cargar_configuracion
from src.backend.services import correo
from src.backend.services.qr import generar_png
from src.backend.tokens import leer_cancelacion

CLAVE = "mailjet-clave-publica-de-prueba"
SECRETO = "mailjet-clave-secreta-de-prueba"
QR_PNG = b"\x89PNG\r\n\x1a\ndatos-qr"


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


DATOS_VALIDOS = {"Messages": [{"Status": "success", "To": [{"Email": "ana@email.com", "MessageID": 12345}]}]}


def _respuesta(status=200, datos=DATOS_VALIDOS, json_invalido=False):
    respuesta = MagicMock()
    respuesta.status_code = status
    if json_invalido:
        respuesta.json.side_effect = requests.exceptions.JSONDecodeError("no es json", "", 0)
    else:
        respuesta.json.return_value = datos
    return respuesta


@pytest.fixture
def app_con_mailjet(app_backend):
    app_backend.config.update(
        MAILJET_API_KEY=CLAVE, MAILJET_SECRET_KEY=SECRETO,
        MAIL_FROM="entradas@cineparadiso.test", FRONTEND_URL="https://cine.test",
    )
    return app_backend


@pytest.fixture
def mailjet(app_con_mailjet):
    with patch("src.backend.services.correo.requests.post", return_value=_respuesta()) as post:
        yield SimpleNamespace(post=post, app=app_con_mailjet)


def _cuerpo_enviado(mailjet):
    [mensaje] = mailjet.post.call_args.kwargs["json"]["Messages"]
    return mensaje


def test_la_app_de_prueba_no_tiene_credenciales_ni_sale_a_la_red(app_backend):
    assert app_backend.config["MAILJET_API_KEY"] == ""
    assert app_backend.config["MAILJET_SECRET_KEY"] == ""
    with patch("src.backend.services.correo.requests.post") as post:
        assert correo.enviar_cancelacion(_compra_de_prueba(), _cliente_de_prueba()) is False
    post.assert_not_called()


def test_enviar_factura_arma_la_peticion_https_a_mailjet_con_todos_los_datos_y_el_qr_embebido(mailjet):
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is True

    mailjet.post.assert_called_once()
    assert mailjet.post.call_args.args == ("https://api.mailjet.com/v3.1/send",)
    opciones = mailjet.post.call_args.kwargs
    assert opciones["auth"] == (CLAVE, SECRETO)
    assert "api-key" not in opciones["headers"]
    assert opciones["timeout"] == 10 == correo.TIMEOUT_SEGUNDOS
    assert opciones["allow_redirects"] is False

    cuerpo = _cuerpo_enviado(mailjet)
    assert cuerpo["From"] == {"Name": "Cine Paradiso", "Email": "entradas@cineparadiso.test"}
    assert cuerpo["To"] == [{"Email": "ana@email.com", "Name": "Ana Pérez"}]
    assert cuerpo["Subject"] == "Tu compra #88 en Cine Paradiso"

    texto, html = cuerpo["TextPart"], cuerpo["HTMLPart"]
    for fragmento in (
        "Ana Pérez", "Volver al futuro", "Paradiso Centro", "Sala 1",
        "10/11 · 20:30", "D5, D6", "Combo pochoclos grande × 2 ($6.500)", "$23.000", "#88",
    ):
        assert fragmento in texto
        assert fragmento in html

    assert "Attachments" not in cuerpo
    [imagen] = cuerpo["InlinedAttachments"]
    assert imagen["Filename"] == "qr-88.png" and imagen["ContentType"] == "image/png"
    assert base64.b64decode(imagen["Base64Content"], validate=True) == QR_PNG
    assert imagen["ContentID"] == "qr-compra-88"
    assert f'src="cid:{imagen["ContentID"]}"' in html
    assert html.count("<img") == 1


def test_enviar_factura_con_un_qr_real_incrusta_un_unico_png_decodificable(mailjet):
    qr_png = generar_png("token-de-prueba-scrum-67")
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), qr_png) is True
    cuerpo = _cuerpo_enviado(mailjet)
    assert "Attachments" not in cuerpo
    [imagen] = cuerpo["InlinedAttachments"]
    assert base64.b64decode(imagen["Base64Content"]) == qr_png


def test_enviar_factura_incluye_enlace_de_cancelacion_firmado_y_qr_por_cid(mailjet):
    correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG)
    cuerpo = _cuerpo_enviado(mailjet)
    texto, html = cuerpo["TextPart"], cuerpo["HTMLPart"]

    with mailjet.app.app_context():
        enlace = correo.enlace_cancelacion(88)
    assert enlace.startswith("https://cine.test/cancelar/")
    assert enlace in texto and f'href="{enlace}"' in html
    assert leer_cancelacion(enlace.rsplit("/", 1)[-1]) == 88

    assert 'src="cid:qr-compra-88"' in html and "data:image" not in html
    assert html.index('src="cid:qr-compra-88"') < html.index(">Película</th>")
    assert "Va adjunto a este correo como imagen PNG." not in html


def test_html_de_la_factura_sigue_el_mockup_incluye_el_qr_y_escapa_los_datos(mailjet):
    compra = _compra_de_prueba(funcion={**_compra_de_prueba()["funcion"], "pelicula": "<b>Volver</b>"})
    correo.enviar_factura(compra, {"nombre": "Ana <script>", "email": "ana@email.com"}, QR_PNG)
    cuerpo = _cuerpo_enviado(mailjet)
    html, texto = cuerpo["HTMLPart"], cuerpo["TextPart"]

    assert "¡Tu compra está confirmada!" in html and "Cancelar compra" in html
    assert "adjunt" not in html and "adjunt" not in texto and "respaldo" not in html
    assert "El código QR de ingreso está en la versión HTML de este correo." in texto
    assert "Podés cancelar hasta 2 horas antes de la función (hasta las 10/11 · 18:30)" in html
    assert html.count("<img") == 1 and "<script" not in html and "<link" not in html and "http://" not in html
    assert "&lt;b&gt;Volver&lt;/b&gt;" in html and "Ana &lt;script&gt;" in html


def test_html_de_la_cancelacion_usa_la_misma_base_y_sin_nombre_no_deja_hola_con_coma_suelta(mailjet):
    correo.enviar_cancelacion(_compra_de_prueba(estado="cancelada"), {"nombre": "", "email": "ana@email.com"})
    cuerpo = _cuerpo_enviado(mailjet)
    html, texto = cuerpo["HTMLPart"], cuerpo["TextPart"]
    assert "Hola, cancelamos tu compra #88." in html and "Hola, cancelamos tu compra #88." in texto
    assert "Se anuló el pago simulado de $23.000." in html and "Total anulado" in html
    assert "QR" in html and "adjunto" not in html and "/cancelar/" not in html and "<img" not in html


def test_enviar_factura_sin_servicios_y_con_una_butaca_adapta_el_texto(mailjet):
    compra = _compra_de_prueba(butacas=["A1"], servicios=[])
    assert correo.enviar_factura(compra, _cliente_de_prueba(), b"png") is True
    cuerpo = _cuerpo_enviado(mailjet)
    assert "Butaca: A1" in cuerpo["TextPart"] and ">Butaca</th>" in cuerpo["HTMLPart"]
    assert "Sin servicios" in cuerpo["TextPart"] and "Sin servicios" in cuerpo["HTMLPart"]


def test_enviar_factura_sin_nombre_de_cliente_omite_name_en_el_destinatario(mailjet):
    cliente = {"nombre": "", "email": "ana@email.com"}
    assert correo.enviar_cancelacion(_compra_de_prueba(), cliente) is True
    assert _cuerpo_enviado(mailjet)["To"] == [{"Email": "ana@email.com"}]


def test_enviar_cancelacion_reutiliza_la_plantilla_sin_qr_ni_enlace_ni_adjunto(mailjet):
    assert correo.enviar_cancelacion(_compra_de_prueba(estado="cancelada"), _cliente_de_prueba()) is True
    cuerpo = _cuerpo_enviado(mailjet)
    assert cuerpo["Subject"] == "Cancelaste tu compra #88 en Cine Paradiso"
    html = cuerpo["HTMLPart"]
    assert "Compra cancelada" in html and "Volver al futuro" in html and "$23.000" in html
    assert "Cancelar compra" not in html and "cid:" not in html
    assert "Attachments" not in cuerpo and "InlinedAttachments" not in cuerpo
    assert "cancelamos tu compra #88" in cuerpo["TextPart"]


@pytest.mark.parametrize("campo", ["MAILJET_API_KEY", "MAILJET_SECRET_KEY", "MAIL_FROM"])
@pytest.mark.parametrize("valor", ["", "  ", None])
def test_enviar_sin_claves_o_sin_remitente_devuelve_false_y_no_usa_la_red(mailjet, campo, valor):
    mailjet.app.config[campo] = valor
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False
    assert correo.enviar_cancelacion(_compra_de_prueba(), _cliente_de_prueba()) is False
    mailjet.post.assert_not_called()


@pytest.mark.parametrize("datos", [
    {}, {"Messages": None}, {"Messages": []}, {"Messages": [None]}, {"Messages": [{"Status": "error"}]},
    {"Messages": [{"Status": "success"}]}, {"Messages": [{"Status": "success", "To": []}]},
    {"Messages": [{"Status": "success", "To": [None]}]}, ["x"], "texto", None,
])
def test_un_200_sin_confirmacion_del_mensaje_devuelve_false(mailjet, datos):
    mailjet.post.return_value = _respuesta(200, datos)
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False


@pytest.mark.parametrize("message_id", [None, "", "0", 0, -1, True, "no-id", {}, []])
def test_un_200_success_sin_message_id_valido_devuelve_false(mailjet, message_id):
    mailjet.post.return_value = _respuesta(datos={"Messages": [{"Status": "success", "To": [{"MessageID": message_id}]}]})
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False


def test_un_200_success_con_message_id_string_es_aceptado(mailjet):
    mailjet.post.return_value = _respuesta(datos={"Messages": [{"Status": "success", "To": [{"MessageID": "12345"}]}]})
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is True


def test_un_200_con_cuerpo_que_no_es_json_devuelve_false(mailjet):
    mailjet.post.return_value = _respuesta(200, json_invalido=True)
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False


@pytest.mark.parametrize("status", [201, 202, 204, 301, 302, 400, 401, 403, 429, 500, 503])
def test_cualquier_status_distinto_de_200_devuelve_false(mailjet, status):
    mailjet.post.return_value = _respuesta(status)
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False
    mailjet.post.assert_called_once()  # sin reintentos automáticos


@pytest.mark.parametrize(
    "excepcion",
    [
        requests.exceptions.Timeout("tiempo agotado"),
        requests.exceptions.ConnectTimeout("no conecta"),
        requests.exceptions.ReadTimeout("no responde"),
        requests.exceptions.ConnectionError("red inalcanzable"),
        requests.exceptions.SSLError("certificado inválido"),
        requests.exceptions.InvalidHeader("cabecera inválida"),
    ],
)
def test_errores_de_red_y_timeouts_devuelven_false_sin_reintentar(mailjet, excepcion):
    mailjet.post.side_effect = excepcion
    assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False
    mailjet.post.assert_called_once()


def test_una_falla_controlada_del_template_devuelve_false_sin_llamar_a_mailjet(mailjet, caplog):
    with patch("src.backend.services.correo.render_template", side_effect=TemplateNotFound("secreto-ana@email.com")):
        with caplog.at_level(logging.DEBUG):
            assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False
    mailjet.post.assert_not_called()
    assert "TemplateNotFound" in caplog.text and "ana@email.com" not in caplog.text


@pytest.mark.parametrize("origen", ["render", "post"])
def test_un_error_inesperado_se_propaga_en_lugar_de_enmascararse(mailjet, origen):
    if origen == "post":
        mailjet.post.side_effect = RuntimeError("bug")
        with pytest.raises(RuntimeError):
            correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG)
    else:
        with patch("src.backend.services.correo.render_template", side_effect=RuntimeError("bug")):
            with pytest.raises(RuntimeError):
                correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG)


def test_el_log_de_un_error_no_filtra_claves_destinatario_token_qr_ni_texto_de_la_excepcion(mailjet, caplog):
    secreto_en_excepcion = f"fallo con claves {CLAVE}:{SECRETO} hacia ana@email.com"
    mailjet.post.side_effect = requests.exceptions.ConnectionError(secreto_en_excepcion)
    with caplog.at_level(logging.DEBUG):
        assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False
    registro = caplog.text
    assert "88" in registro and "ConnectionError" in registro
    with mailjet.app.app_context():
        token = correo.enlace_cancelacion(88).rsplit("/", 1)[-1]
    for secreto in (CLAVE, SECRETO, "ana@email.com", "Ana", token, base64.b64encode(QR_PNG).decode(), secreto_en_excepcion):
        assert secreto not in registro


@pytest.mark.parametrize("status, datos", [(401, {"message": "Key not found"}), (403, {}), (200, {})])
def test_el_log_de_un_rechazo_solo_tiene_compra_y_status(mailjet, caplog, status, datos):
    mailjet.post.return_value = _respuesta(status, datos)
    with caplog.at_level(logging.DEBUG):
        assert correo.enviar_factura(_compra_de_prueba(), _cliente_de_prueba(), QR_PNG) is False
    registro = caplog.text
    assert "88" in registro
    if status != 200:
        assert f"HTTP {status}" in registro
    for secreto in (CLAVE, SECRETO, "ana@email.com", "Key not found"):
        assert secreto not in registro


def test_configuracion_lee_mailjet_y_mail_from_sin_valores_por_defecto_y_quita_barra_de_frontend_url(monkeypatch):
    monkeypatch.setattr("src.backend.config.load_dotenv", lambda: None)
    monkeypatch.setenv("MAILJET_API_KEY", f"  {CLAVE}  ")
    monkeypatch.setenv("MAILJET_SECRET_KEY", f"  {SECRETO}  ")
    monkeypatch.setenv("MAIL_FROM", " entradas@cine.com ")
    monkeypatch.setenv("FRONTEND_URL", "https://cine.com/")
    config = cargar_configuracion()
    assert config["MAILJET_API_KEY"] == CLAVE
    assert config["MAILJET_SECRET_KEY"] == SECRETO
    assert config["MAIL_FROM"] == "entradas@cine.com"
    assert config["FRONTEND_URL"] == "https://cine.com"


def test_configuracion_sin_variables_deja_clave_y_remitente_vacios_y_sin_claves_smtp(monkeypatch):
    monkeypatch.setattr("src.backend.config.load_dotenv", lambda: None)
    for nombre in ("MAILJET_API_KEY", "MAILJET_SECRET_KEY", "MAIL_FROM", "SMTP_USER", "SMTP_HOST"):
        monkeypatch.delenv(nombre, raising=False)
    config = cargar_configuracion()
    assert config["MAILJET_API_KEY"] == "" and config["MAILJET_SECRET_KEY"] == "" and config["MAIL_FROM"] == ""
    assert not [clave for clave in config if clave.startswith("SMTP_")]


@pytest.mark.skipif(
    not os.getenv("MAILJET_PRUEBA_DESTINO"),
    reason="Definir MAILJET_PRUEBA_DESTINO=casilla@real y ambas claves Mailjet más MAIL_FROM en .env "
           "para probar un envío real.",
)
def test_envio_real_a_casilla_configurada():
    from src.backend.app import create_app

    app = create_app()
    # El ejemplo no debe firmar un enlace capaz de cancelar una compra real con el mismo id.
    app.config["SECRET_KEY"] = "prueba-de-email-sin-compra-real"
    destino = os.environ["MAILJET_PRUEBA_DESTINO"]
    with app.app_context():
        qr_png = generar_png("token-de-prueba-scrum-67")
        assert correo.enviar_factura(_compra_de_prueba(), {"nombre": "Equipo", "email": destino}, qr_png) is True
