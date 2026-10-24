"""Registro de blueprints. Un archivo por módulo para trabajar en paralelo
sin modificar los mismos archivos."""
from backend.routes.admin import admin_bp
from backend.routes.auth import auth_bp
from backend.routes.cartelera import cartelera_bp
from backend.routes.compras import compras_bp
from backend.routes.dashboards import dashboards_bp
from backend.routes.salud import salud_bp


def registrar_rutas(app):
    for blueprint in (salud_bp, auth_bp, cartelera_bp, compras_bp, admin_bp, dashboards_bp):
        app.register_blueprint(blueprint)
