"""Punto de entrada del backend (API REST en JSON).

Ejecutar: flask --app src.backend.app run --port 5000 --debug
"""

from flask import Flask

from src.backend.config import cargar_configuracion
from src.backend.errores import registrar_manejadores
from src.backend.routes import registrar_rutas


def create_app():
    app = Flask(__name__)
    app.config.update(cargar_configuracion())
    app.json.ensure_ascii = False
    registrar_manejadores(app)
    registrar_rutas(app)
    return app
