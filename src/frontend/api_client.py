"""Cliente único para hablar con el backend.

Toda comunicación con la API se hace desde Python con requests: el navegador
nunca hace peticiones al backend (ni fetch, ni axios, ni XMLHttpRequest).
"""
import requests
from flask import abort, current_app, jsonify, make_response, session

TIMEOUT_SEGUNDOS = 5


def _cabeceras():
    token = session.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def llamar(metodo, ruta, json=None, params=None):
    """Llama al backend y devuelve el JSON de la respuesta.

    Interrumpe la petición con un error HTTP JSON si el backend falla.
    """
    url = f"{current_app.config['BACKEND_URL']}{ruta}"
    try:
        respuesta = requests.request(
            metodo, url, json=json, params=params, headers=_cabeceras(), timeout=TIMEOUT_SEGUNDOS
        )
    except requests.RequestException as error:
        abort(make_response(jsonify({"error": {
            "codigo": "BACKEND_NO_DISPONIBLE",
            "mensaje": "No se pudo conectar con el servidor.",
        }}), 503))

    if respuesta.ok:
        return respuesta.json() if respuesta.content else None

    try:
        detalle = respuesta.json().get("error", {})
    except ValueError:
        detalle = {}
    abort(make_response(jsonify({"error": {
        "codigo": detalle.get("codigo", "ERROR"),
        "mensaje": detalle.get("mensaje", "El servidor respondió con un error."),
    }}), respuesta.status_code))
