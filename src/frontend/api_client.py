"""Cliente único para hablar con el backend.

Toda comunicación con la API se hace desde Python con requests: el navegador
nunca hace peticiones al backend (ni fetch, ni axios, ni XMLHttpRequest).
"""
import requests
from flask import current_app, session

TIMEOUT_SEGUNDOS = 5


class ErrorBackend(Exception):
    """El backend respondió con error o no está disponible."""

    def __init__(self, status, codigo, mensaje):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje


def _cabeceras():
    token = session.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def llamar(metodo, ruta, json=None, params=None):
    """Llama al backend y devuelve el JSON de la respuesta.

    Lanza ErrorBackend si la respuesta no es 2xx o si el backend no responde.
    """
    url = f"{current_app.config['BACKEND_URL']}{ruta}"
    try:
        respuesta = requests.request(
            metodo, url, json=json, params=params, headers=_cabeceras(), timeout=TIMEOUT_SEGUNDOS
        )
    except requests.RequestException as error:
        raise ErrorBackend(503, "BACKEND_NO_DISPONIBLE", "No se pudo conectar con el servidor.") from error

    if respuesta.ok:
        return respuesta.json() if respuesta.content else None

    try:
        detalle = respuesta.json().get("error", {})
    except ValueError:
        detalle = {}
    raise ErrorBackend(
        respuesta.status_code,
        detalle.get("codigo", "ERROR"),
        detalle.get("mensaje", "El servidor respondió con un error."),
    )
