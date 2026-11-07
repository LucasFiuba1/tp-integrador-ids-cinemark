"""Datos de ejemplo de las pantallas maquetadas que todavía no tienen su endpoint.

Tienen la misma forma que las respuestas de la API, así al conectar cada pantalla solo se reemplaza la llamada por
llamar(...). Están en un solo lugar para que el sitio del cliente y el backoffice no repitan los mismos datos.
"""


def servicios_ejemplo():
    """Forma de GET /api/admin/servicios (activos e inactivos); GET /api/servicios devuelve solo los activos."""
    return [
        {"id": 1, "nombre": "Combo pochoclos grande", "descripcion": "Pochoclos grandes y gaseosa de 500 ml",
         "precio": 6500.00, "activo": True},
        {"id": 2, "nombre": "Gaseosa", "descripcion": "Gaseosa de 500 ml", "precio": 2500.00, "activo": True},
        {"id": 3, "nombre": "Estacionamiento", "descripcion": "Estacionamiento durante la función",
         "precio": 3000.00, "activo": True},
        {"id": 4, "nombre": "Acceso VIP", "descripcion": "Butaca reclinable y servicio en sala",
         "precio": 8000.00, "activo": False},
    ]
