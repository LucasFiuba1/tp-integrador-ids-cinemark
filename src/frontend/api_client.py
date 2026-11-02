"""Cliente único para hablar con el backend.

Toda comunicación con la API se hace desde Python con requests: el navegador
nunca hace peticiones al backend (ni fetch, ni axios, ni XMLHttpRequest).
"""
import requests
from flask import abort, current_app, session

from src.frontend.sesion import ir_al_login

TIMEOUT_SEGUNDOS = 5


def _error(status, codigo, mensaje):
    return {"status": status, "codigo": codigo, "mensaje": mensaje}


def _cabeceras():
    token = session.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def llamar(metodo, ruta, json=None, params=None):
    """Llama al backend y devuelve la tupla (datos, error).

    Si la respuesta es 2xx, datos es el JSON recibido y error es None. Si no es 2xx o el
    backend no responde, datos es None y error es {"status", "codigo", "mensaje"}.

    Si mandamos un token y el backend responde 401, la sesión venció: corta el request con abort
    y redirige al login, así ninguna ruta tiene que revisarlo. Sin token (por ejemplo, un login con
    la contraseña equivocada), el 401 vuelve como cualquier otro error.
    """
    url = f"{current_app.config['BACKEND_URL']}{ruta}"
    cabeceras = _cabeceras()
    try:
        respuesta = requests.request(
            metodo, url, json=json, params=params, headers=cabeceras, timeout=TIMEOUT_SEGUNDOS
        )
    except requests.RequestException:
        return None, _error(503, "BACKEND_NO_DISPONIBLE", "No se pudo conectar con el servidor.")

    if respuesta.ok:
        return (respuesta.json() if respuesta.content else None), None

    if respuesta.status_code == 401 and cabeceras:
        abort(ir_al_login("Tu sesión venció. Ingresá de nuevo."))

    try:
        detalle = respuesta.json().get("error", {})
    except ValueError:
        detalle = {}
    return None, _error(
        respuesta.status_code,
        detalle.get("codigo", "ERROR"),
        detalle.get("mensaje", "El servidor respondió con un error."),
    )
