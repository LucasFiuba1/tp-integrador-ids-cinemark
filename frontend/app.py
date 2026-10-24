"""Punto de entrada del frontend (sitio del cliente y backoffice).

Ejecutar: flask --app frontend.app run --port 5001 --debug
"""
from flask import Flask, render_template

from frontend.config import cargar_configuracion
from frontend.routes import registrar_rutas


def create_app():
    app = Flask(__name__)
    app.config.update(cargar_configuracion())
    registrar_rutas(app)

    @app.errorhandler(404)
    def no_encontrado(_error):
        return render_template("errores/404.html"), 404

    @app.errorhandler(500)
    def error_interno(_error):
        return render_template("errores/500.html"), 500

    return app
