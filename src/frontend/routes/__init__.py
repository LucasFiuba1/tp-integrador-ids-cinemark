"""Registro de blueprints del frontend: sitio público y backoffice."""
from src.frontend.routes.backoffice import backoffice_bp
from src.frontend.routes.publico import publico_bp


def registrar_rutas(app):
    app.register_blueprint(publico_bp)
    app.register_blueprint(backoffice_bp)
