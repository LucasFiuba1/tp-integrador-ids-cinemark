from flask import Blueprint, jsonify

salud_bp = Blueprint("salud", __name__, url_prefix="/api")


@salud_bp.get("/salud")
def salud():
    """Permite verificar que la API está levantada."""
    return jsonify({"estado": "ok"})
