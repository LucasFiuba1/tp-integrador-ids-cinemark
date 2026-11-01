"""Lógica de negocio, organizada por funcionalidad.

Las rutas delegan aquí los casos de uso. Los servicios usan src.backend.db
para acceder a MySQL y error_api (src.backend.errores) para cortar con errores de negocio.
Las operaciones que deben ser atómicas comparten una misma transacción.
"""
