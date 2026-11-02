"""Formato único de respuestas de error en JSON.

Todas las respuestas de error tienen la forma:
    {"error": {"codigo": "BUTACA_OCUPADA", "mensaje": "..."}}
"""
from flask import abort, jsonify, make_response
from werkzeug.exceptions import HTTPException


def respuesta_error(status, codigo, mensaje):
    return jsonify({"error": {"codigo": codigo, "mensaje": mensaje}}), status


def error_api(status, codigo, mensaje):
    """Corta el request con un error de negocio en el formato JSON único.

    flask.abort lanza una HTTPException que lleva la respuesta armada adentro;
    manejar_error_http la devuelve tal cual.
    """
    abort(make_response(respuesta_error(status, codigo, mensaje)))


MENSAJES_HTTP = {
    400: ("DATOS_INVALIDOS", "Los datos enviados no son válidos."),
    401: ("NO_AUTENTICADO", "Tenés que iniciar sesión."),
    403: ("SIN_PERMISO", "No tenés permiso para esta acción."),
    404: ("NO_ENCONTRADO", "El recurso solicitado no existe."),
    405: ("METODO_NO_PERMITIDO", "El método HTTP no está permitido para esta ruta."),
}


def registrar_manejadores(app):
    """Registra los manejadores para que ningún error devuelva HTML."""

    @app.errorhandler(HTTPException)
    def manejar_error_http(error):
        if error.response is not None:
            return error.response
        codigo, mensaje = MENSAJES_HTTP.get(
            error.code, (error.name.upper().replace(" ", "_"), error.description)
        )
        return respuesta_error(error.code, codigo, mensaje)

    @app.errorhandler(Exception)
    def manejar_error_inesperado(error):
        app.logger.exception(error)
        return respuesta_error(500, "ERROR_INTERNO", "Ocurrió un error inesperado.")
